from pathlib import Path

from core import __main__ as sidecar
from core import doctor
from core.settings import Settings

CLI = {
    "provider": "claude",
    "label": "Claude Code",
    "installed": True,
    "logged_in": True,
    "steps": "",
}


def test_the_vault_check_names_each_gap(tmp_path: Path) -> None:
    assert doctor.check_vault(None, None)["state"] == "bad"
    assert "does not exist" in doctor.check_vault(tmp_path / "gone", None)["found"]
    assert doctor.check_vault(tmp_path, None)["state"] == "warn"
    ok = doctor.check_vault(tmp_path, 16)
    assert ok["state"] == "ok" and ok["found"].startswith("16 notes") and ok["fix"] == ""


def test_agent_programs_one_row_each_and_a_loud_row_when_none_is_installed() -> None:
    rows = doctor.check_clis(
        [
            CLI,
            {
                **CLI,
                "label": "Codex",
                "installed": True,
                "logged_in": False,
                "steps": "Run `codex login`.",
            },
            {**CLI, "label": "Gemini CLI", "installed": True, "logged_in": None},
            {
                **CLI,
                "label": "Antigravity",
                "installed": False,
                "steps": "Install Antigravity first.",
            },
        ]
    )
    assert [(r["name"], r["state"]) for r in rows] == [
        ("Claude Code program", "ok"),
        ("Codex program", "bad"),
        ("Gemini CLI program", "ok"),
        ("Antigravity program", "warn"),
    ]
    assert rows[1]["fix"] == "Run `codex login`."
    none = doctor.check_clis([{**CLI, "installed": False, "steps": "Install it."}])
    assert none[0]["name"] == "Agent programs" and none[0]["state"] == "bad"


def test_the_sandbox_row_follows_the_two_switches() -> None:
    assert doctor.check_sandbox(False, False)["state"] == "warn"
    assert "off" in doctor.check_sandbox(True, False)["found"]
    assert "on for agents" in doctor.check_sandbox(True, True)["found"]


def test_the_doctor_method_lists_every_check_with_a_count(tmp_path: Path) -> None:
    session = sidecar.Session(tmp_path, Settings(), emit=lambda e: None)
    report = session.dispatch({"method": "doctor"})
    names = [r["name"] for r in report["checks"]]
    for needed in (
        "Backend",
        "Vault",
        "Disk space",
        "Agent sandbox",
        "Backend log",
        "Recorded errors",
    ):
        assert needed in names
    assert sum(report["summary"].values()) == len(report["checks"])
    assert report["summary"]["bad"] >= 1  # no vault is set in this session
    assert all(
        r["fix"] for r in report["checks"] if r["state"] == "bad"
    )  # every gap says what to do
