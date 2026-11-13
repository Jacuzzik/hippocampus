"""The connector rows, tested with a fake Ollama server, a fake gh program and fake config files: no accounts."""

import json
import stat
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import pytest

from core import activity, connectors
from core.__main__ import Session
from core.connectors import STATES
from core.settings import Settings


class FakeOllama(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = json.dumps({"models": [{"name": "qwen2.5:1.5b"}, {"name": "llama3.2:3b"}]}).encode()
        self.send_response(200 if self.path == "/api/tags" else 404)
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


@pytest.fixture
def ollama_host():
    server = HTTPServer(("127.0.0.1", 0), FakeOllama)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{server.server_port}"
    server.shutdown()


def test_ollama_is_connected_only_when_the_server_answers(ollama_host: str) -> None:
    got = connectors.ollama(ollama_host, "qwen2.5:1.5b")
    assert got["state"] == "Connected"
    assert got["details"] == ["qwen2.5:1.5b", "llama3.2:3b"]


def test_ollama_with_a_missing_model_needs_setup_and_says_the_pull_command(
    ollama_host: str,
) -> None:
    got = connectors.ollama(ollama_host, "mistral:7b")
    assert got["state"] == "Needs setup"
    assert "ollama pull mistral:7b" in got["reason"]


def test_ollama_that_does_not_answer_is_not_connected() -> None:
    got = connectors.ollama("http://127.0.0.1:9", "x", timeout=1.0)
    assert got["state"] == "Not connected"
    assert "ollama serve" in got["reason"]


def test_a_host_that_is_not_http_is_an_error_not_a_call() -> None:
    assert connectors.ollama("file:///etc/passwd", "x")["state"] == "Error"


def fake_gh(tmp_path: Path, exit_code: int, text: str) -> Path:
    script = tmp_path / "gh"
    script.write_text(f"#!/bin/sh\necho '{text}'\nexit {exit_code}\n", encoding="utf-8")
    script.chmod(script.stat().st_mode | stat.S_IEXEC)
    return script


def test_github_connected_shows_the_account(tmp_path: Path) -> None:
    gh = fake_gh(tmp_path, 0, "Logged in to github.com account octo (keyring)")
    got = connectors.github(which=lambda _name: str(gh))
    assert got["state"] == "Connected"
    assert got["reason"] == "Logged in to github.com as octo."


def test_github_not_logged_in_says_the_command(tmp_path: Path) -> None:
    gh = fake_gh(tmp_path, 1, "You are not logged into any GitHub hosts")
    got = connectors.github(which=lambda _name: str(gh))
    assert got["state"] == "Not connected" and "gh auth login" in got["reason"]


def test_github_missing_and_github_too_slow() -> None:
    assert connectors.github(which=lambda _name: None)["state"] == "Needs setup"

    def slow(*_args: object, **_kwargs: object) -> object:
        raise subprocess.TimeoutExpired("gh", 1)

    got = connectors.github(timeout=1, which=lambda _name: "/bin/gh", run=slow)
    assert got["state"] == "Error" and "did not answer within 1 seconds" in got["reason"]


def test_mcp_lists_user_and_project_servers_with_secrets_masked(tmp_path: Path) -> None:
    home, project = tmp_path / "home", tmp_path / "proj"
    home.mkdir()
    project.mkdir()
    (home / ".claude.json").write_text(
        json.dumps(
            {
                "mcpServers": {
                    "files": {
                        "command": "npx",
                        "args": [
                            "-y",
                            "server-files",
                            "--api-key",
                            "sk-live-SECRETSECRETSECRETSECRET",
                            "token=abc123",
                        ],
                        "env": {"GITHUB_TOKEN": "ghp_VERYSECRETVALUE"},
                    },
                    "web": {"url": "https://user:pass@example.com/mcp?key=SECRETQUERY"},
                },
                "projects": {
                    "/work/other": {"mcpServers": {"db": {"command": "dbtool", "args": []}}}
                },
            }
        ),
        encoding="utf-8",
    )
    (project / ".mcp.json").write_text(
        json.dumps({"mcpServers": {"local": {"command": "run"}}}), encoding="utf-8"
    )
    got = connectors.mcp(home, [project])
    text = json.dumps(got)
    for secret in ("SECRETSECRET", "abc123", "ghp_VERYSECRETVALUE", "SECRETQUERY", "user:pass"):
        assert secret not in text
    assert (
        "files: npx -y server-files --api-key *** token=*** (env: GITHUB_TOKEN) [user]"
        in got["details"]
    )
    assert "web: https://example.com/mcp [user]" in got["details"]
    assert "db: dbtool [project other]" in got["details"]
    assert "local: run [project proj]" in got["details"]
    assert got["state"] == "Not connected" and "4 servers listed" in got["reason"]


def test_mcp_with_no_files_and_with_a_broken_file(tmp_path: Path) -> None:
    assert connectors.mcp(tmp_path, [])["details"] == []
    (tmp_path / ".claude.json").write_text("{not json", encoding="utf-8")
    got = connectors.mcp(tmp_path, [])
    assert got["state"] == "Error" and "Could not read .claude.json" in got["reason"]


def test_every_row_has_every_field_and_a_known_state(tmp_path: Path) -> None:
    rows = [
        connectors.mcp(tmp_path, []),
        connectors.webhooks(2),
        connectors.jobs(3, 1),
        *connectors.planned(),
    ]
    for one in rows:
        assert {
            "id",
            "kind",
            "name",
            "what",
            "state",
            "reason",
            "needs",
            "details",
            "checked",
        } <= set(one)
        assert one["name"] and one["what"] and one["reason"]
        assert one["state"] in STATES
    assert len({one["id"] for one in rows}) == len(rows)
    # A connector with no calls built never claims to work.
    assert all(
        one["state"] == "Needs setup" and one["kind"] == "card" for one in connectors.planned()
    )


def test_the_session_lists_rows_checks_once_and_logs_without_secrets(
    tmp_path: Path, ollama_host: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    calls = []
    real = connectors.ollama
    monkeypatch.setattr(connectors, "ollama", lambda *a, **k: calls.append(1) or real(*a, **k))
    monkeypatch.setattr(
        connectors, "github", lambda: connectors.row("github", "GitHub", "x", "Connected", "ok")
    )
    session = Session(
        storage=tmp_path / "storage",
        settings=Settings(ollama_host=ollama_host),
        settings_path=tmp_path / "settings.toml",
    )
    first = session.dispatch({"method": "connectors"})["connectors"]
    assert {one["id"] for one in first} >= {
        "ollama",
        "github",
        "mcp",
        "webhooks",
        "jobs",
        "slack",
        "gmail",
    }
    assert next(one for one in first if one["id"] == "ollama")["state"] == "Connected"
    session.dispatch({"method": "connectors"})
    assert len(calls) == 1, "a second call within seconds uses the remembered answer"
    session.dispatch({"method": "connectors", "fresh": True})
    assert len(calls) == 1, "fresh still waits out the minimum gap, so there is no tight loop"
    log = [
        row
        for row in activity.read(tmp_path / "storage", "setting")
        if "connectors checked" in row["text"]
    ]
    assert len(log) == 1 and "ollama Connected" in log[0]["text"]
    session.close()


def test_a_failing_service_is_not_asked_again_within_a_minute(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    calls = []

    def down(*_a: object, **_k: object) -> connectors.Row:
        calls.append(1)
        return connectors.row("ollama", "Ollama", "x", "Not connected", "nothing answered")

    monkeypatch.setattr(connectors, "ollama", down)
    monkeypatch.setattr(
        connectors, "github", lambda: connectors.row("github", "GitHub", "x", "Connected", "ok")
    )
    session = Session(
        storage=tmp_path / "storage", settings=Settings(), settings_path=tmp_path / "s.toml"
    )
    for _ in range(3):
        session.dispatch({"method": "connectors"})
    assert len(calls) == 1
    session.close()
