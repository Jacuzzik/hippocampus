"""Autonomy levels (7.20), the custom command engine (7.02) and the app's protection in the sandbox (D.09)."""

from pathlib import Path

import pytest

from core import autonomy, sandbox, terminal
from core.settings import ROOT


@pytest.fixture
def clis(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(terminal.shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(terminal.cli_sessions, "FILE", tmp_path / "sessions.json")


@pytest.mark.parametrize(
    ("provider", "level", "expected"),
    [
        ("claude", "edits", ["--permission-mode", "acceptEdits"]),
        ("codex", "ask", ["--ask-for-approval", "on-request"]),
        ("codex", "full", ["--sandbox", "workspace-write", "--ask-for-approval", "never"]),
        ("gemini-cli", "edits", ["--approval-mode", "auto_edit"]),
        ("gemini-cli", "full", ["--approval-mode", "yolo"]),
        ("antigravity", "edits", ["--mode", "accept-edits"]),
        ("ollama", "full", []),
    ],
)
def test_each_level_becomes_the_clis_own_flags(
    provider: str, level: str, expected: list[str]
) -> None:
    assert autonomy.flags(provider, level) == expected


def test_the_app_folder_always_asks_and_full_needs_a_fence() -> None:
    assert autonomy.effective("claude", "full", sandboxed=True, folder_in_app=True) == "ask"
    assert autonomy.effective("claude", "full", sandboxed=True, folder_in_app=False) == "full"
    # Without the sandbox only Codex has its own workspace fence; the rest run as "edits".
    assert autonomy.effective("gemini-cli", "full", sandboxed=False, folder_in_app=False) == "edits"
    assert autonomy.effective("codex", "full", sandboxed=False, folder_in_app=False) == "full"
    assert autonomy.effective("claude", "nonsense", sandboxed=False, folder_in_app=False) == "edits"
    assert "limited" in autonomy.describe("gemini-cli", "full", "edits")
    assert autonomy.describe("ollama", "full", "full") == "Autonomy: set by the program itself"


def test_the_flags_reach_the_command_line(clis: None) -> None:
    gemini = terminal._command("ada", "gemini-cli", "m", level="edits")
    assert gemini[-2:] == ["--approval-mode", "auto_edit"]
    blocked = terminal._command("ada", "codex", block_tools=True, level="full")
    assert "never" not in blocked and blocked[-2:] == ["--sandbox", "read-only"]
    claude = terminal._command("ada", "claude", shell=True, level="full")
    allowed = claude[claude.index("--allowedTools") + 1 : claude.index("--disallowedTools")]
    assert "Bash" in allowed and claude[claude.index("--permission-mode") + 1] == "acceptEdits"
    # The deny rules still come after, so the app folder stays closed at "full".
    assert f"Bash(* {ROOT}*)" in claude


def test_a_folder_inside_the_app_counts_but_the_vault_does_not(tmp_path: Path) -> None:
    assert terminal._folder_in_app(str(ROOT / "app"), None) is True
    assert (
        terminal._folder_in_app(str(ROOT / "data" / "brains"), str(ROOT / "data" / "brains"))
        is False
    )
    assert terminal._folder_in_app(str(tmp_path), None) is False


def test_a_custom_command_is_split_without_a_shell(clis: None) -> None:
    assert terminal._command("ada", "custom", command="aider --model 'x y'") == [
        "/usr/bin/aider",
        "--model",
        "x y",
    ]
    with pytest.raises(RuntimeError, match="no custom command"):
        terminal._command("ada", "custom", command="  ")
    with pytest.raises(RuntimeError, match="cannot be read"):
        terminal._command("ada", "custom", command="aider 'open")


def test_a_custom_command_needs_the_sandbox(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sandbox, "available", lambda: False)
    with pytest.raises(RuntimeError, match="only inside the sandbox"):
        terminal.Terminals(emit=lambda e: None).start("ada", "custom", 24, 80, command="aider")


def test_the_installed_app_and_its_data_are_read_only_in_the_sandbox(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(sandbox.shutil, "which", lambda name: f"/usr/bin/{name}")
    home = tmp_path / "home"
    for name in sandbox.APP_PATHS:
        (home / name).mkdir(parents=True)
    vault = home / ".local/share/dev.hippocampus.desktop/brains"
    vault.mkdir()
    argv = sandbox.wrap(["x"], app_root=tmp_path / "app", home=home, writable=[vault])
    pairs = [(argv[i], argv[i + 1]) for i in range(len(argv) - 1)]
    for name in sandbox.APP_PATHS:
        assert ("--ro-bind", str(home / name)) in pairs
    # The vault inside the data folder stays writable, because the deeper rule comes later.
    assert argv.index(str(vault)) > argv.index(str(home / ".local/share/dev.hippocampus.desktop"))
    assert ("--bind", str(vault)) in pairs


@pytest.mark.parametrize(("provider", "program"), [("codex", "codex"), ("gemini-cli", "gemini")])
def test_every_flag_and_value_is_in_the_installed_clis_own_help(
    provider: str, program: str
) -> None:
    """10.10: Codex's workspace-write sandbox and Gemini's approval modes are checked against the CLI's help,
    not remembered. Skipped on a computer without that CLI."""
    import shutil
    import subprocess

    binary = shutil.which(program)
    if binary is None:
        pytest.skip(f"{program} is not installed here")
    help_text = subprocess.run(  # noqa: S603 (a fixed program and flag)
        [binary, "--help"], capture_output=True, text=True, timeout=30, check=False
    ).stdout
    for level in autonomy.LEVELS:
        for word in autonomy.flags(provider, level):
            # A flag is named in the help as it is; a value such as auto_edit may be written with or without "_".
            assert word.replace("_", "") in help_text.replace("_", ""), (provider, word)


def test_opencode_gets_no_permission_flag_and_says_its_own_rules_apply(clis: None) -> None:
    """10.10: OpenCode has no per-run permission setting except --auto (approve all), which the app never passes."""
    argv = terminal._command("ada", "gemini", "gemini-2.5-pro", level="full")
    assert "--auto" not in argv and not any("approv" in part for part in argv)
    assert autonomy.flags("gemini", "full") == []
    assert autonomy.describe("gemini", "full", "full") == "Autonomy: set by the program itself"
