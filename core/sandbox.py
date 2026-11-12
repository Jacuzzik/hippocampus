"""Runs an agent's command-line program inside an operating-system sandbox (bubblewrap).

Word patterns such as "no rm" are best effort: a shell can always reach a file no pattern names.
The sandbox is the real fence. Inside it:
  - the whole system is read-only, except the user's home folder;
  - the app's own folder is read-only, so nothing the agent runs can change or delete the app;
  - the hive (every agent's inbox and outbox) is read-only, except the agent's own outbox;
  - private folders (SSH keys and the like) are empty;
  - the agent sees only its own processes, so it cannot stop the app or another agent.
"""

import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

# Folders under the home folder that hold keys. Inside the sandbox each one is empty.
PRIVATE = (".ssh", ".gnupg", ".aws", ".config/gh", ".password-store")


@lru_cache(maxsize=1)
def available() -> bool:
    """True when bubblewrap is installed and this system lets it start. Checked once."""
    binary = shutil.which("bwrap")
    if binary is None:
        return False
    try:
        done = subprocess.run(
            [binary, "--ro-bind", "/", "/", "--unshare-pid", "--proc", "/proc", "true"],
            capture_output=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return False
    return done.returncode == 0


def wrap(
    argv: list[str],
    *,
    app_root: Path,
    home: Path,
    writable: list[Path] | None = None,
    readonly: list[Path] | None = None,
    cwd: Path | None = None,
) -> list[str]:
    """The same command, started inside the sandbox. The home folder is writable; the app folder and
    the `readonly` list are closed; each `writable` folder is opened. A rule for a deeper folder
    wins over one for a folder that holds it."""
    binary = shutil.which("bwrap")
    if binary is None:
        raise RuntimeError("bubblewrap (bwrap) is not installed, so the agent sandbox cannot start.")
    args = [
        binary,
        "--die-with-parent",
        # Its own process list: the app, the backend and other agents are not visible and cannot be signalled.
        "--unshare-pid",
        "--ro-bind", "/", "/",
        "--dev-bind", "/dev", "/dev",
        "--proc", "/proc",
        "--tmpfs", "/tmp",
    ]  # fmt: skip
    app_root = app_root.resolve()
    rules: list[tuple[Path, str]] = [(home.resolve(), "--bind"), (app_root, "--ro-bind")]
    rules += [(path.resolve(), "--ro-bind") for path in readonly or [] if path.exists()]
    for path in writable or []:
        if not path.exists():
            continue
        path = path.resolve()
        # A writable folder that holds the app (the home folder, say) must not reopen it, and the app
        # folder itself is never writable. Deeper rules are applied last, so they win.
        if path == app_root:
            continue
        rules.append((path, "--bind"))
    # Shallow paths first: a rule for a folder inside another always wins over the outer one,
    # whatever order the caller listed them in.
    for path, flag in sorted(rules, key=lambda rule: len(rule[0].parts)):
        args += [flag, str(path), str(path)]
    for name in PRIVATE:
        path = home / name
        if path.is_dir():
            args += ["--tmpfs", str(path)]
    if cwd is not None and cwd.is_dir():
        args += ["--chdir", str(cwd)]
    return [*args, "--", *argv]


def policy_lines(*, shell: bool, sandboxed: bool, blocked: bool, app_root: Path) -> list[str]:
    """What an agent may do, in plain words. The same lines go into the agent's briefing and the
    Settings page, so neither can say something the real rules do not."""
    if blocked:
        return [
            "Tools are blocked for this agent: no shell, no file writes, no web and no note tools.",
        ]
    lines = []
    if shell:
        lines.append(
            "Shell: allowed for simple tasks. Not allowed: rm, rmdir, mv, cp, git, sudo, chmod, chown, curl, wget, dd, "
            "kill, pkill, process listings, the claude command, and any command that names the app folder."
        )
    else:
        lines.append("Shell: not available to this agent.")
    lines.append(f"The app folder ({app_root}) cannot be read or edited with the file tools.")
    if sandboxed:
        lines += [
            "Your program runs in a sandbox: the app folder and the system are read-only, whatever command is used.",
            "You see only your own processes. Private folders such as SSH keys are empty.",
            "Other agents' inboxes and outboxes are read-only. You write only to your own outbox.",
        ]
    return lines
