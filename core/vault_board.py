"""The Vault dashboard: counts read from the notes index, and a summary the main agent writes.

The counts are exact. The summary is the agent's reading of the vault (what matters, what is in
progress), kept in data/storage/vault_insights.json and shown with the time it was written.
"""

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any

IMPORTANT = {"important", "priority", "urgent", "star", "starred", "pinned", "key"}
PROJECT_TAGS = {"project", "projects"}
PROJECT_FOLDERS = {"project", "projects", "1-projects", "01-projects", "01 projects"}
DAILY = re.compile(r"(^|/)\d{4}-\d{2}-\d{2}[^/]*\.md$")
WEEK_NS = 7 * 24 * 3600 * 1_000_000_000


def _tag(tag: str) -> str:
    return tag.lower().lstrip("#").split("/")[0]


def stats(
    graph: dict[str, Any], mtimes: dict[str, int], broken: int, now_ns: int
) -> dict[str, Any]:
    """Exact numbers about the vault, from the graph (notes, tags, links) and each note's change time."""
    nodes = graph.get("nodes", [])
    linked: set[str] = set()
    for source, target in graph.get("edges", []):
        linked.update((source, target))
    projects: set[str] = set()
    folders: Counter[str] = Counter()
    tags: Counter[str] = Counter()
    important = daily = memory = 0
    for node in nodes:
        path = PurePosixPath(node["id"])
        folders[path.parts[0] if len(path.parts) > 1 else "(top level)"] += 1
        node_tags = {_tag(t) for t in node.get("tags", [])}
        tags.update(node_tags)
        if node_tags & IMPORTANT:
            important += 1
        if DAILY.search(node["id"]):
            daily += 1
        if node.get("memory"):
            memory += 1
        parts = [part.lower() for part in path.parts]
        for i, part in enumerate(parts[:-1]):
            if part in PROJECT_FOLDERS:
                # A project is each folder or note straight inside the projects folder.
                projects.add("/".join(path.parts[: i + 2]))
                break
        else:
            if node_tags & PROJECT_TAGS:
                projects.add(node["id"])
    recent = sorted(
        ((mtimes.get(n["id"], 0), n["id"], n.get("title") or n["id"]) for n in nodes), reverse=True
    )
    return {
        "notes": len(nodes),
        "links": len(graph.get("edges", [])),
        "orphans": sum(1 for n in nodes if n["id"] not in linked),
        "broken": broken,
        "important": important,
        "projects": len(projects),
        "project_names": sorted(PurePosixPath(p).stem for p in projects)[:12],
        "daily": daily,
        "memory": memory,
        "tags": len(tags),
        "top_tags": tags.most_common(8),
        "folders": folders.most_common(8),
        "changed_week": sum(1 for t, _, _ in recent if now_ns - t <= WEEK_NS),
        "recent": [
            {
                "path": path,
                "title": title,
                "at": datetime.fromtimestamp(t / 1e9).isoformat(timespec="minutes"),
            }
            for t, path, title in recent[:6]
            if t
        ],
    }


def load_insights(path: Path) -> dict[str, Any] | None:
    """The agent's summary, or None when it has not written one or wrote something unreadable."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    numbers = [
        {
            "label": str(n.get("label"))[:60],
            "value": str(n.get("value"))[:30],
            "note": str(n.get("note") or "")[:120],
        }
        for n in data.get("numbers") or []
        if isinstance(n, dict) and n.get("label") is not None and n.get("value") is not None
    ][:12]
    highlights = [str(h)[:300] for h in data.get("highlights") or [] if isinstance(h, str)][:10]
    return {
        "summary": str(data.get("summary") or "")[:1500],
        "numbers": numbers,
        "highlights": highlights,
        "generated_at": str(data.get("generated_at") or ""),
    }


def request_text(target: Path) -> tuple[str, str]:
    """The objective and output of the task that asks the main agent for the summary."""
    objective = (
        "Read the notes vault and sum it up for the user's Vault dashboard: what the vault holds, "
        "which projects are active, which notes matter most, and what looks unfinished or stale."
    )
    output = (
        f"Write one JSON file at {target} with these keys: "
        '"generated_at" (ISO time now), "summary" (two to four plain sentences), '
        '"numbers" (up to 12 objects {"label", "value", "note"}, for example active projects, '
        "important notes, open to-dos, notes waiting for review, ideas), and "
        '"highlights" (up to 10 short lines naming notes or projects that need attention). '
        "Count from the notes themselves; do not guess. Then reply done."
    )
    return objective, output
