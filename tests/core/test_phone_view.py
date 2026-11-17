"""The phone's screen inside the app (DB.09): frames, approval and the token on the local stream."""

import urllib.error
import urllib.request

import pytest

from core import phone, phone_view


def test_whole_jpegs_are_cut_off_and_a_partial_one_waits() -> None:
    buffer = bytearray(b"junk\xff\xd8one\xff\xd9\xff\xd8two\xff\xd9\xff\xd8thr")
    assert phone_view.jpeg_frames(buffer) == [b"\xff\xd8one\xff\xd9", b"\xff\xd8two\xff\xd9"]
    assert bytes(buffer) == b"\xff\xd8thr"


def _adb(*args: object, **kwargs: object) -> object:
    class Done:
        returncode = 0
        stdout = "List of devices attached\nR58M123ABC device model:SM_A525F\n"
        stderr = ""

    return Done()


def test_showing_needs_the_click_and_a_ready_phone() -> None:
    shown: list[str] = []
    which = lambda name: f"/usr/bin/{name}"  # noqa: E731
    with pytest.raises(ValueError, match="approval"):
        phone.view("R58M123ABC", False, which, _adb, shown.append)
    with pytest.raises(ValueError, match="not connected"):
        phone.view("OTHER", True, which, _adb, shown.append)
    phone.view("R58M123ABC", True, which, _adb, shown.append)
    assert shown == ["R58M123ABC"]


def test_the_stream_refuses_a_wrong_token_and_serves_the_right_one() -> None:
    view = phone_view.View.__new__(phone_view.View)
    view.serial, view.alive, view.frame = "R58M123ABC", True, b"\xff\xd8x\xff\xd9"
    view.changed = phone_view.threading.Condition()
    phone_view._views["R58M123ABC"] = view
    try:
        url = phone_view.url("R58M123ABC")
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(url.split("?")[0] + "?t=wrong", timeout=5)
        with urllib.request.urlopen(url, timeout=5) as reply:
            assert reply.headers["Content-Type"].startswith("multipart/x-mixed-replace")
            assert b"\xff\xd8x\xff\xd9" in reply.read1(4096)
            view.alive = False
            with view.changed:
                view.changed.notify_all()
    finally:
        phone_view._views.pop("R58M123ABC", None)
