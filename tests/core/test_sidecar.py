import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from core import __version__


def run_core(*args: str, stdin: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, "-m", "core", *args],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )


def test_version_flag() -> None:
    result = run_core("--version")
    assert result.returncode == 0
    assert result.stdout.strip() == __version__


def test_serve_announces_ready_and_exits_on_stdin_eof() -> None:
    result = run_core("serve")
    assert result.returncode == 0
    first_line = result.stdout.splitlines()[0]
    assert json.loads(first_line) == {"status": "ready", "version": __version__}


def test_command_is_required() -> None:
    result = run_core()
    assert result.returncode != 0


def serve_with(stdin: str, *args: str, storage: str) -> list[dict[str, Any]]:
    result = subprocess.run(
        [sys.executable, "-m", "core", "serve", *args, "--storage", storage],
        input=stdin,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return [json.loads(line) for line in result.stdout.splitlines()]


def test_serve_answers_graph_for_the_vault_it_was_given(
    sample_vault: tuple[Path, Any], storage: Path
) -> None:
    vault, _ = sample_vault
    lines = serve_with('{"id": 1, "method": "graph"}\n', str(vault), storage=str(storage))
    assert lines[0] == {"status": "ready", "version": __version__}
    assert lines[1]["id"] == 1
    graph = lines[1]["result"]
    assert graph["nodes"] and graph["edges"]
    assert {"id", "title", "tags"} <= graph["nodes"][0].keys()


def test_serve_opens_a_vault_on_request(sample_vault: tuple[Path, Any], storage: Path) -> None:
    vault, _ = sample_vault
    stdin = json.dumps({"id": "a", "method": "open", "vault": str(vault)}) + "\n"
    stdin += '{"id": "b", "method": "graph"}\n'
    lines = serve_with(stdin, storage=str(storage))
    assert lines[1]["id"] == "a" and lines[1]["result"]["added_files"] > 0
    assert lines[1]["result"]["vault"] == str(vault.resolve())
    assert lines[2]["id"] == "b" and lines[2]["result"]["nodes"]


def test_serve_graph_without_a_vault_is_an_error_not_a_crash(storage: Path) -> None:
    lines = serve_with('{"id": 7, "method": "graph"}\n', storage=str(storage))
    assert lines[1] == {"id": 7, "error": "no vault is open"}


def test_bad_json_gets_an_error_line_and_the_loop_keeps_going(
    sample_vault: tuple[Path, Any], storage: Path
) -> None:
    vault, _ = sample_vault
    stdin = 'not json\n[1, 2]\n{"id": 3, "method": "nope"}\n{"id": 4, "method": "graph"}\n'
    lines = serve_with(stdin, str(vault), storage=str(storage))
    assert lines[1]["id"] is None and lines[1]["error"].startswith("invalid JSON")
    assert lines[2] == {"id": None, "error": "request must be a JSON object"}
    assert lines[3] == {"id": 3, "error": "unknown method: 'nope'"}
    assert lines[4]["id"] == 4 and "result" in lines[4]


def test_open_rejects_a_missing_folder(storage: Path, tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    stdin = json.dumps({"id": 1, "method": "open", "vault": str(missing)}) + "\n"
    lines = serve_with(stdin, storage=str(storage))
    assert lines[1] == {"id": 1, "error": f"vault folder not found: {missing}"}


def test_serve_reads_the_settings_file_it_is_given(
    tmp_path: Path, sample_vault: tuple[Path, Any], storage: Path
) -> None:
    # A packaged app keeps config/ and the vault in the user data folder, not the repo.
    vault, _ = sample_vault
    settings = tmp_path / "config" / "settings.toml"
    settings.parent.mkdir()
    settings.write_text(f'[vault]\npath = "{vault.relative_to(tmp_path)}"\n'.replace("\\", "/"))
    lines = serve_with(
        '{"id": 1, "method": "graph"}\n', "--settings", str(settings), storage=str(storage)
    )
    assert lines[1]["result"]["nodes"]
