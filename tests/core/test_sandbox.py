import os
import subprocess
from pathlib import Path

import pytest

from core import sandbox

pytestmark = pytest.mark.skipif(not sandbox.available(), reason="bubblewrap cannot start on this machine")


@pytest.fixture
def world(tmp_path: Path) -> dict[str, Path]:
    """A pretend home with an app folder, a hive, an agent folder and a private folder."""
    home = tmp_path / "home"
    paths = {
        "home": home,
        "app": home / "app",
        "index": home / "app" / "data" / "index",
        "hive": home / ".hippocampus" / "hive",
        "outbox": home / ".hippocampus" / "hive" / "ada" / "outbox",
        "other": home / ".hippocampus" / "hive" / "bob" / "inbox",
        "folder": home / "work" / "ada",
        "ssh": home / ".ssh",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    (paths["app"] / "main.py").write_text("print('app')\n", encoding="utf-8")
    (paths["ssh"] / "id_ed25519").write_text("secret key\n", encoding="utf-8")
    return paths


def run(world: dict[str, Path], script: str) -> subprocess.CompletedProcess[str]:
    argv = sandbox.wrap(
        ["sh", "-c", script],
        app_root=world["app"],
        home=world["home"],
        readonly=[world["hive"]],
        writable=[world["index"], world["outbox"]],
        cwd=world["folder"],
    )
    return subprocess.run(argv, capture_output=True, text=True, timeout=30, check=False)


def test_the_agent_can_work_in_its_own_folder_and_outbox(world: dict[str, Path]) -> None:
    done = run(world, f"pwd && echo hi > note.txt && echo '{{}}' > {world['outbox']}/m.json && echo x > {world['index']}/db")
    assert done.returncode == 0, done.stderr
    assert done.stdout.strip() == str(world["folder"])
    assert (world["folder"] / "note.txt").read_text() == "hi\n"
    assert (world["outbox"] / "m.json").exists() and (world["index"] / "db").exists()


@pytest.mark.parametrize(
    "script",
    [
        "echo x > {app}/new.py",  # write into the app
        "echo x >> {app}/main.py",  # change an app file
        "rm {app}/main.py",  # delete an app file
        "rm -rf {app}",  # delete the app
        "mv {app}/main.py {app}/gone.py",  # rename inside the app
        "echo x > {other}/fake.json",  # write into another agent's inbox
        "echo x > /usr/hippo-test",  # write into the system
    ],
)
def test_nothing_the_agent_runs_can_change_the_app_or_the_system(world: dict[str, Path], script: str) -> None:
    done = run(world, script.format(app=world["app"], other=world["other"]))
    assert done.returncode != 0
    assert (world["app"] / "main.py").read_text() == "print('app')\n"
    assert not (world["app"] / "new.py").exists() and not (world["other"] / "fake.json").exists()


def test_private_folders_are_empty_inside(world: dict[str, Path]) -> None:
    done = run(world, f"ls -A {world['ssh']} | wc -l")
    assert done.stdout.strip() == "0"
    assert (world["ssh"] / "id_ed25519").exists()  # still there outside


def test_the_agent_cannot_see_or_stop_the_app(world: dict[str, Path]) -> None:
    me = os.getpid()  # stands in for the app: a process outside the sandbox
    done = run(world, f"kill -0 {me}; echo status=$?; ls /proc | grep -c '^[0-9]'")
    lines = done.stdout.split()
    assert lines[0] != "status=0"  # the signal did not reach this process
    assert int(lines[1]) < 10  # only its own few processes are listed
    os.kill(me, 0)  # and this process is still here


def test_the_policy_text_matches_the_switches() -> None:
    root = Path("/opt/app")
    assert sandbox.policy_lines(shell=False, sandboxed=False, blocked=True, app_root=root) == [
        "Tools are blocked for this agent: no shell, no file writes, no web and no note tools."
    ]
    open_shell = sandbox.policy_lines(shell=True, sandboxed=True, blocked=False, app_root=root)
    assert open_shell[0].startswith("Shell: allowed") and any("sandbox" in line for line in open_shell)
    no_shell = sandbox.policy_lines(shell=False, sandboxed=False, blocked=False, app_root=root)
    assert no_shell[0] == "Shell: not available to this agent." and not any("sandbox" in line for line in no_shell)
