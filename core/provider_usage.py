"""Tokens used per provider and model, read from the logs each AI tool keeps on this computer.

Nothing is estimated: a provider that logs no token counts says so. Read only; nothing here reaches a
network. Claude Code and Codex logs can be large, so each file is read once and remembered until it
changes (its size or time changes).

  Claude Code  ~/.claude/projects/*/*.jsonl          each reply's usage, with its model
  Codex        ~/.codex/sessions/Y/M/D/rollout-*.jsonl each turn's token_count, model from turn_context
  OpenCode     ~/.local/share/opencode/opencode.db   each assistant message's tokens and model
  Gemini CLI   ~/.gemini/tmp/*/chats/*.json          each reply's tokens and model
  Antigravity  ~/.gemini/antigravity-cli/conversations  conversations only: it keeps no token counts here
  This app     data/storage/usage.jsonl              the in-app assistant and helpers, per agent
"""

import json
import shutil
import sqlite3
import threading
from collections import defaultdict
from collections.abc import Callable, Iterator
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

DAYS = 14
# day (YYYY-MM-DD) -> model -> tokens
Usage = dict[str, dict[str, int]]
_cache: dict[Path, tuple[float, int, Usage]] = {}
_lock = threading.Lock()


def _day(stamp: object) -> str | None:
    if isinstance(stamp, int | float):  # milliseconds since 1970
        return datetime.fromtimestamp(stamp / 1000).astimezone().date().isoformat()
    if not isinstance(stamp, str) or not stamp:
        return None
    try:
        return datetime.fromisoformat(stamp.replace("Z", "+00:00")).astimezone().date().isoformat()
    except ValueError:
        return None


def _cached(path: Path, read: Callable[[Path], Usage]) -> Usage:
    try:
        stat = path.stat()
    except OSError:
        return {}
    with _lock:
        hit = _cache.get(path)
        if hit and hit[0] == stat.st_mtime and hit[1] == stat.st_size:
            return hit[2]
    try:
        usage = read(path)
    except (OSError, ValueError):
        usage = {}
    with _lock:
        _cache[path] = (stat.st_mtime, stat.st_size, usage)
    return usage


def _recent(paths: Iterator[Path], since: date) -> list[Path]:
    floor = datetime.combine(since, datetime.min.time()).timestamp()
    out = []
    for path in paths:
        try:
            if path.stat().st_mtime >= floor:
                out.append(path)
        except OSError:
            continue
    return out


def _add(usage: Usage, day: str | None, model: str, tokens: int) -> None:
    if day and tokens > 0:
        usage.setdefault(day, {})
        usage[day][model or "unknown"] = usage[day].get(model or "unknown", 0) + tokens


def _claude_file(path: Path) -> Usage:
    usage: Usage = {}
    seen: set[str] = set()
    with path.open(encoding="utf-8", errors="replace") as lines:
        for line in lines:
            if '"usage"' not in line:
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            message = row.get("message")
            if not isinstance(message, dict) or not isinstance(message.get("usage"), dict):
                continue
            key = str(message.get("id") or row.get("uuid") or len(seen))
            if key in seen:  # one reply is logged once per content block
                continue
            seen.add(key)
            counts = message["usage"]
            tokens = sum(
                int(counts.get(name) or 0)
                for name in (
                    "input_tokens",
                    "output_tokens",
                    "cache_read_input_tokens",
                    "cache_creation_input_tokens",
                )
            )
            model = str(message.get("model") or "")
            if model != "<synthetic>":
                _add(usage, _day(row.get("timestamp")), model, tokens)
    return usage


def _codex_file(path: Path) -> Usage:
    usage: Usage = {}
    model = ""
    with path.open(encoding="utf-8", errors="replace") as lines:
        for line in lines:
            try:
                row = json.loads(line)
            except ValueError:
                continue
            payload = row.get("payload") or {}
            if not isinstance(payload, dict):
                continue
            if row.get("type") == "turn_context" and payload.get("model"):
                model = str(payload["model"])
            elif payload.get("type") == "token_count":
                last = (payload.get("info") or {}).get("last_token_usage") or {}
                _add(usage, _day(row.get("timestamp")), model, int(last.get("total_tokens") or 0))
    return usage


def _gemini_file(path: Path) -> Usage:
    usage: Usage = {}
    data = json.loads(path.read_text(encoding="utf-8"))
    for message in data.get("messages") or [] if isinstance(data, dict) else []:
        tokens = message.get("tokens") if isinstance(message, dict) else None
        if isinstance(tokens, dict):
            _add(
                usage,
                _day(message.get("timestamp")),
                str(message.get("model") or ""),
                int(tokens.get("total") or 0),
            )
    return usage


def _merge(parts: list[Usage]) -> Usage:
    total: Usage = {}
    for part in parts:
        for day, models in part.items():
            for model, tokens in models.items():
                _add(total, day, model, tokens)
    return total


def _opencode(db: Path, since: date) -> Usage:
    usage: Usage = {}
    if not db.is_file():
        return usage
    floor = int(datetime.combine(since, datetime.min.time()).timestamp() * 1000)
    try:
        with sqlite3.connect(f"file:{db}?mode=ro", uri=True) as conn:
            rows = conn.execute(
                "select time_created, json_extract(data, '$.modelID'), "
                "json_extract(data, '$.tokens.total') from message where time_created >= ?",
                (floor,),
            ).fetchall()
    except sqlite3.Error:
        return usage
    for created, model, tokens in rows:
        _add(usage, _day(created), str(model or ""), int(tokens or 0))
    return usage


def _ledger(path: Path, since: date) -> Usage:
    """The app's own ledger: one line per in-app reply, by agent (it does not record the model)."""
    usage: Usage = {}
    if not path.is_file():
        return usage
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        day = _day(row.get("ts"))
        if day and day >= since.isoformat():
            _add(usage, day, f"agent {row.get('agent') or '?'}", int(row.get("tokens") or 0))
    return usage


def _summary(
    provider: str, name: str, found: bool, usage: Usage, today: date, note: str = ""
) -> dict[str, Any]:
    month = today.replace(day=1).isoformat()
    week = (today - timedelta(days=6)).isoformat()
    models: dict[str, int] = defaultdict(int)
    totals = {"today": 0, "week": 0, "month": 0}
    for day, by_model in usage.items():
        tokens = sum(by_model.values())
        if day == today.isoformat():
            totals["today"] += tokens
        if day >= week:
            totals["week"] += tokens
        if day >= month:
            totals["month"] += tokens
            for model, count in by_model.items():
                models[model] += count
    days = [(today - timedelta(days=DAYS - 1 - i)).isoformat() for i in range(DAYS)]
    return {
        "id": provider,
        "name": name,
        "found": found,
        "note": note,
        **totals,
        "models": sorted(
            ({"model": m, "tokens": t} for m, t in models.items()), key=lambda r: -r["tokens"]
        ),
        "days": [sum(usage.get(day, {}).values()) for day in days],
    }


def report(storage: Path, home: Path | None = None, today: date | None = None) -> dict[str, Any]:
    """Every provider found on this computer, with tokens today, in 7 days and this month, by model."""
    home = home or Path.home()
    today = today or datetime.now().astimezone().date()
    since = min(today.replace(day=1), today - timedelta(days=DAYS))
    providers = []

    claude_dir = home / ".claude" / "projects"
    claude = _merge(
        [_cached(p, _claude_file) for p in _recent(claude_dir.glob("*/*.jsonl"), since)]
    )
    providers.append(
        _summary(
            "claude",
            "Claude Code",
            claude_dir.is_dir() or bool(shutil.which("claude")),
            claude,
            today,
        )
    )

    codex_dir = home / ".codex" / "sessions"
    codex = _merge(
        [_cached(p, _codex_file) for p in _recent(codex_dir.glob("*/*/*/rollout-*.jsonl"), since)]
    )
    providers.append(
        _summary("codex", "Codex", codex_dir.is_dir() or bool(shutil.which("codex")), codex, today)
    )

    opencode_db = home / ".local" / "share" / "opencode" / "opencode.db"
    providers.append(
        _summary(
            "opencode",
            "OpenCode",
            opencode_db.is_file() or bool(shutil.which("opencode")),
            _opencode(opencode_db, since),
            today,
        )
    )

    gemini_dir = home / ".gemini" / "tmp"
    gemini = _merge(
        [_cached(p, _gemini_file) for p in _recent(gemini_dir.glob("*/chats/*.json"), since)]
    )
    providers.append(
        _summary(
            "gemini",
            "Gemini CLI",
            gemini_dir.is_dir() or bool(shutil.which("gemini")),
            gemini,
            today,
        )
    )

    antigravity = home / ".gemini" / "antigravity-cli" / "conversations"
    chats = len(list(antigravity.glob("*.db"))) if antigravity.is_dir() else 0
    providers.append(
        _summary(
            "antigravity",
            "Antigravity",
            antigravity.is_dir() or bool(shutil.which("antigravity")),
            {},
            today,
            note=f"{chats} conversations on this computer. Antigravity keeps no token counts here, so its use cannot be shown."
            if antigravity.is_dir()
            else "",
        )
    )

    providers.append(
        _summary(
            "app",
            "This app (assistant and helpers)",
            True,
            _ledger(storage / "usage.jsonl", since),
            today,
            note="Counted per agent; the app does not log which model answered.",
        )
    )
    return {"today": today.isoformat(), "days": DAYS, "providers": providers}
