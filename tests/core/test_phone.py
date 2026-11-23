"""The Phone dashboard lists Android devices with adb and mirrors one with scrcpy, on approval only."""

import subprocess
from types import SimpleNamespace

import pytest

from core import phone

LIST = (
    "List of devices attached\n"
    "R58M123ABC             device usb:1-2 product:a52 model:SM_A525F device:a52q transport_id:1\n"
    "192.168.1.20:5555      unauthorized transport_id:2\n"
    "\n"
)


def _adb(stdout: str = LIST, code: int = 0, stderr: str = ""):
    return lambda *a, **k: SimpleNamespace(returncode=code, stdout=stdout, stderr=stderr)


def _both(_name: str) -> str:
    return "/usr/bin/tool"


class FakeProcess:
    def __init__(self) -> None:
        self.ended = False

    def poll(self) -> int | None:
        return 0 if self.ended else None

    def terminate(self) -> None:
        self.ended = True


@pytest.fixture(autouse=True)
def _no_mirrors():
    phone._running.clear()
    yield
    phone._running.clear()


def test_status_lists_devices_with_state_and_model() -> None:
    found = phone.status(_both, _adb())
    assert (found["adb"], found["scrcpy"], found["error"]) == (True, True, "")
    assert found["devices"] == [
        {"serial": "R58M123ABC", "state": "device", "model": "SM A525F"},
        {"serial": "192.168.1.20:5555", "state": "unauthorized", "model": ""},
    ]
    assert found["mirroring"] == []


def test_status_says_when_a_tool_is_missing_or_adb_fails() -> None:
    def never(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("adb must not run")

    missing = phone.status(lambda _name: None, never)
    assert missing["adb"] is False
    assert "not installed" in missing["error"]
    assert phone.status(_both, _adb("", 1, "daemon not running"))["error"] == "daemon not running"

    def slow(*_args: object, **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired("adb", 10)

    assert phone.status(_both, slow)["error"] == "adb took too long to answer."


def test_mirroring_starts_scrcpy_once_with_light_settings_and_stops() -> None:
    started: list[list[str]] = []

    def popen(command: list[str], **_kwargs: object) -> FakeProcess:
        started.append(command)
        return FakeProcess()

    found = phone.mirror("R58M123ABC", True, _both, _adb(), popen)
    assert found["mirroring"] == ["R58M123ABC"]
    assert started[0][:3] == ["scrcpy", "--serial", "R58M123ABC"]
    assert started[0][started[0].index("--window-title") + 1] == "Hippocampus: SM A525F"
    assert "--no-audio" in started[0]
    phone.mirror("R58M123ABC", True, _both, _adb(), popen)
    assert len(started) == 1  # already mirrored: no second window
    process = phone._running["R58M123ABC"]
    assert phone.stop("R58M123ABC", _both, _adb())["mirroring"] == []
    assert process.ended


def test_mirroring_is_refused_without_approval_or_for_a_device_that_cannot_be_used() -> None:
    def never(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("scrcpy must not start")

    with pytest.raises(ValueError, match="approval"):
        phone.mirror("R58M123ABC", None, _both, _adb(), never)
    for bad in ("", "a b", "x; rm -rf ~", "--help", None):
        with pytest.raises(ValueError, match="not a device serial|not connected"):
            phone.mirror(bad, True, _both, _adb(), never)
    with pytest.raises(ValueError, match="not connected"):
        phone.mirror("OTHER", True, _both, _adb(), never)
    with pytest.raises(ValueError, match="USB debugging"):
        phone.mirror("192.168.1.20:5555", True, _both, _adb(), never)
    with pytest.raises(ValueError, match="scrcpy is not installed"):
        phone.mirror(
            "R58M123ABC", True, lambda name: None if name == "scrcpy" else "/x", _adb(), never
        )


def test_a_mirror_whose_window_was_closed_is_no_longer_listed() -> None:
    phone.mirror("R58M123ABC", True, _both, _adb(), lambda *a, **k: FakeProcess())
    phone._running["R58M123ABC"].ended = True
    assert phone.status(_both, _adb())["mirroring"] == []


def test_control_turns_taps_swipes_keys_and_text_into_adb_input() -> None:
    import subprocess as sp

    calls: list[list[str]] = []

    def run(args: list[str], **_kwargs: object) -> sp.CompletedProcess[str]:
        calls.append(args)
        out = "Physical size: 1080x2400\n" if args[-2:] == ["wm", "size"] else ""
        return sp.CompletedProcess(args, 0, out, "")

    have = lambda _name: "/usr/bin/adb"  # noqa: E731
    phone.control("ABC", {"kind": "tap", "x": 0.5, "y": 0.25}, True, have, run)
    assert calls[-1][-3:] == ["tap", "540", "600"]
    phone.control(
        "ABC",
        {"kind": "swipe", "x": 0, "y": 0, "x2": 1, "y2": 1, "ms": 300, "landscape": True},
        True,
        have,
        run,
    )
    assert calls[-1][-5:] == ["0", "0", "2399", "1079", "300"]
    phone.control("ABC", {"kind": "key", "key": "home"}, True, have, run)
    assert calls[-1][-2:] == ["keyevent", "3"]
    phone.control("ABC", {"kind": "text", "text": "hi there"}, True, have, run)
    assert calls[-1][-1] == "hi%sthere"
    for bad, reason in [
        ({"kind": "tap", "x": 2, "y": 0}, "from 0 to 1"),
        ({"kind": "key", "key": "nuke"}, "must be one of"),
        ({"kind": "text", "text": ""}, "1 to 500"),
        ({"kind": "fly"}, "tap, swipe, key or text"),
    ]:
        with pytest.raises(ValueError, match=reason):
            phone.control("ABC", bad, True, have, run)
    with pytest.raises(ValueError, match="approval"):
        phone.control("ABC", {"kind": "key", "key": "home"}, None, have, run)
