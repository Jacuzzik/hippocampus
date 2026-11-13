from pathlib import Path

import pytest

from core import __main__ as sidecar
from core import sandbox, terminal
from core.settings import ROOT, Settings, load_settings, save_agent_shell


def bash_rules(argv: list[str]) -> list[str]:
    start = argv.index("--disallowedTools") + 1
    return [rule for rule in argv[start:] if rule.startswith("Bash")]


@pytest.fixture
def claude(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(terminal.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(terminal.cli_sessions, "FILE", tmp_path / "sessions.json")


def test_without_the_switch_a_normal_agent_has_no_shell(claude: None) -> None:
    assert bash_rules(terminal._command("ada", "claude")) == ["Bash"]


def test_with_the_switch_every_agent_gets_the_same_fenced_shell(claude: None) -> None:
    agent = bash_rules(terminal._command("ada", "claude", shell=True))
    main = bash_rules(terminal._command("hippoherman", "claude"))
    assert agent == main  # one list for all, so behaviour is predictable
    assert "Bash(rm:*)" in agent and "Bash(git:*)" in agent and "Bash(kill:*)" in agent
    assert f"Bash(* {ROOT}*)" in agent  # no command may name the app folder
    assert "Bash" not in agent  # the blanket ban is gone


def test_block_tools_still_removes_the_shell(claude: None) -> None:
    assert "Bash" in terminal._command("ada", "claude", block_tools=True, shell=True)


def test_only_a_tested_cli_runs_in_the_sandbox(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sandbox, "available", lambda: True)
    assert terminal.sandbox_for("claude") is True
    assert terminal.sandbox_for("codex") is False  # not tested inside the sandbox yet
    monkeypatch.setattr(sandbox, "available", lambda: False)
    assert terminal.sandbox_for("claude") is False  # no sandbox, so no shell for normal agents


def test_the_sandboxed_command_closes_the_app_and_opens_only_the_agents_own_outbox(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    hive = tmp_path / "hive"
    monkeypatch.setattr(terminal, "HIVE_DIR", hive)
    # The rules are built the same with or without bubblewrap on this machine.
    monkeypatch.setattr(sandbox.shutil, "which", lambda name: f"/usr/bin/{name}")
    argv = terminal._sandboxed(["claude"], "ada", str(tmp_path), None)
    assert argv[-2:] == ["--", "claude"]
    text = " ".join(argv)
    assert f"--ro-bind {ROOT} {ROOT}" in text and f"--ro-bind {hive} {hive}" in text
    assert f"--bind {hive / 'ada' / 'outbox'} {hive / 'ada' / 'outbox'}" in text
    assert "--unshare-pid" in argv and "--die-with-parent" in argv
    # The app folder is closed after the home folder is opened, so the later rule wins.
    assert argv.index(str(ROOT)) > argv.index(str(Path.home()))


def test_the_switch_is_saved_and_the_rules_are_reported_in_plain_words(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "config" / "settings.toml"
    path.parent.mkdir()
    path.write_text('[network]\nmode = "off"\n', encoding="utf-8")
    session = sidecar.Session(tmp_path, Settings(), emit=lambda e: None, settings_path=path)
    monkeypatch.setattr(sandbox, "available", lambda: True)
    off = session.dispatch({"method": "settings"})["shell"]
    assert off["on"] is False and off["agents"][0] == "Shell: not available to this agent."
    on = session.dispatch({"method": "set_agent_shell", "on": True})
    assert (
        on["on"] is True
        and on["agents"][0].startswith("Shell: allowed")
        and any("sandbox" in line for line in on["agents"])
    )
    assert (
        load_settings(path).agent_shell is True and load_settings(path).network_mode == "off"
    )  # the rest of the file is kept
    with pytest.raises(ValueError):
        session.dispatch({"method": "set_agent_shell", "on": "yes"})
    save_agent_shell(False, path)
    assert load_settings(path).agent_shell is False


def test_a_working_folder_inside_the_app_or_the_hive_is_not_made_writable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    hive = tmp_path / "hive"
    monkeypatch.setattr(terminal, "HIVE_DIR", hive)
    # The rules are built the same with or without bubblewrap on this machine.
    monkeypatch.setattr(sandbox.shutil, "which", lambda name: f"/usr/bin/{name}")
    (hive / "bob" / "inbox").mkdir(parents=True)

    def binds(folder: Path, vault: Path | None = None) -> list[str]:
        argv = terminal._sandboxed(["claude"], "ada", str(folder), str(vault) if vault else None)
        return [argv[i + 1] for i, flag in enumerate(argv) if flag == "--bind"]

    assert str(ROOT / "app") not in binds(ROOT / "app")  # app code
    assert str(ROOT) not in binds(ROOT)
    assert str(hive / "bob" / "inbox") not in binds(hive / "bob" / "inbox")  # another agent's inbox
    vault = ROOT / "data" / "brains"
    if vault.is_dir():
        assert str(vault) in binds(
            vault, vault
        )  # the vault is the one place inside the app an agent writes
    assert str(tmp_path) in binds(tmp_path)  # an ordinary folder outside both
