"""MCP servers per agent: written only to the agent's own .mcp.json, secrets masked, other keys kept."""

import json
from pathlib import Path

import pytest

import core.__main__ as sidecar
from core import added_agents, mcp_config
from core.settings import Settings


def test_add_list_and_remove_keep_other_keys(tmp_path: Path) -> None:
    (tmp_path / ".mcp.json").write_text(json.dumps({"other": 1}), encoding="utf-8")
    rows = mcp_config.add(
        tmp_path, "fs", "npx -y server-fs --token abcdefabcdefabcdefabcdefabcdef /data"
    )
    assert rows == [
        {"name": "fs", "kind": "stdio", "command": "npx -y server-fs --token *** /data", "env": ""}
    ]
    mcp_config.add(tmp_path, "docs", "https://mcp.example.com/sse?key=hidden")
    saved = json.loads((tmp_path / ".mcp.json").read_text(encoding="utf-8"))
    assert saved["other"] == 1 and saved["mcpServers"]["docs"]["type"] == "http"
    assert mcp_config.servers(tmp_path)[1]["command"] == "https://mcp.example.com/sse"
    assert [r["name"] for r in mcp_config.remove(tmp_path, "fs")] == ["docs"]


def test_bad_names_addresses_and_files_are_refused(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="letters"):
        mcp_config.add(tmp_path, "../x", "npx a")
    with pytest.raises(ValueError, match="https"):
        mcp_config.add(tmp_path, "web", "http://plain.example.com")
    with pytest.raises(ValueError, match="No server"):
        mcp_config.remove(tmp_path, "nope")
    (tmp_path / ".mcp.json").write_text("{broken", encoding="utf-8")
    with pytest.raises(ValueError, match="left alone"):
        mcp_config.add(tmp_path, "fs", "npx a")
    assert (tmp_path / ".mcp.json").read_text(encoding="utf-8") == "{broken"


def test_only_an_added_agent_with_a_folder_has_servers(tmp_path: Path) -> None:
    session = sidecar.Session(tmp_path / "s", Settings())
    folder = tmp_path / "ada"
    folder.mkdir()
    added_agents.save(session.agents_path, [{"id": "ada", "name": "Ada", "folder": str(folder)}])
    session.dispatch({"method": "mcp_add", "agent": "ada", "name": "fs", "line": "npx fs"})
    assert session.dispatch({"method": "mcp_servers", "agent": "ada"})["servers"][0]["name"] == "fs"
    with pytest.raises(ValueError, match="added agent"):
        session.dispatch({"method": "mcp_servers", "agent": "hippoherman"})
