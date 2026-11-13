"""No call may hang the app: every program the backend starts and every web request has a time limit."""

import ast
from pathlib import Path

from core.settings import ROOT

BLOCKING = {
    "subprocess.run",
    "subprocess.call",
    "subprocess.check_call",
    "subprocess.check_output",
    "urllib.request.urlopen",
    "urlopen",
}
# Waits that are bounded another way, each with the reason.
BOUNDED_ELSEWHERE = {
    ("ai/providers/claude_cli.py", "proc.communicate"),  # inside asyncio.wait_for(timeout=...)
    ("core/__main__.py", "watcher.ready.wait"),  # raced against the watcher task itself
    ("core/terminal.py", "proc.wait"),  # its own thread, after the terminal has closed
}


def _unbounded(path: Path) -> list[str]:
    found = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if not isinstance(node, ast.Call):
            continue
        name = ast.unparse(node.func)
        waits = name.endswith((".communicate", ".wait"))
        if name not in BLOCKING and not waits:
            continue
        limited = any(key.arg == "timeout" for key in node.keywords) or (waits and node.args)
        relative = path.relative_to(ROOT).as_posix()
        if not limited and (relative, name) not in BOUNDED_ELSEWHERE:
            found.append(f"{relative}:{node.lineno} {name}")
    return found


def test_every_program_and_web_call_has_a_time_limit() -> None:
    files = [file for folder in ("core", "ai", "tools") for file in (ROOT / folder).rglob("*.py")]
    assert len(files) > 20
    assert [line for file in files for line in _unbounded(file)] == []
