"""The Phone dashboard: Android devices seen by adb, and screen mirroring with scrcpy.

The screen is shown inside the app by core/phone_view.py (view only). scrcpy's own window, which takes
taps and keys, is still there for full control. Either starts only on the user's click (the request must
carry approve: true), with small settings so a weak computer copes.
"""

import atexit
import re
import shlex
import shutil
import subprocess
from collections.abc import Callable
from typing import Any

from core import phone_view

SERIAL = re.compile(r"^[A-Za-z0-9._:-]{1,64}$")
SECONDS = 10
# Light settings: a smaller picture, 30 frames a second, no sound.
SCRCPY_ARGS = ("--max-size", "1024", "--max-fps", "30", "--no-audio")
_running: dict[str, Any] = {}


def _devices(run: Callable[..., Any]) -> list[dict[str, str]]:
    done = run(
        ["adb", "devices", "-l"], capture_output=True, text=True, timeout=SECONDS, check=False
    )
    if done.returncode != 0:
        raise ValueError(done.stderr.strip() or "adb could not list the devices.")
    devices = []
    for line in done.stdout.splitlines()[1:]:
        parts = line.split()
        if len(parts) < 2 or not SERIAL.match(parts[0]):
            continue
        model = next((part[6:] for part in parts[2:] if part.startswith("model:")), "")
        devices.append({"serial": parts[0], "state": parts[1], "model": model.replace("_", " ")})
    return devices


def _alive() -> list[str]:
    for serial in [serial for serial, process in _running.items() if process.poll() is not None]:
        del _running[serial]
    return sorted(_running)


def status(
    which: Callable[[str], str | None] = shutil.which,
    run: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    """What is installed, the devices adb sees and which are being mirrored. Never raises for a missing tool."""
    found: dict[str, Any] = {
        "adb": which("adb") is not None,
        "scrcpy": which("scrcpy") is not None,
        "devices": [],
        "mirroring": _alive(),
        # Phones shown inside the app, each with the address of its picture stream.
        "showing": phone_view.showing(),
        "error": "",
    }
    if not found["adb"]:
        found["error"] = "adb is not installed. Install the Android platform tools."
        return found
    try:
        found["devices"] = _devices(run)
    except subprocess.TimeoutExpired:
        found["error"] = "adb took too long to answer."
    except ValueError as error:
        found["error"] = str(error)
    return found


def _ready(
    serial: object, approve: object, which: Callable[[str], str | None], run: Callable[..., Any]
) -> dict[str, str]:
    """The device row, after the approval, the serial and the tools are checked."""
    if approve is not True:
        raise ValueError("mirroring a phone needs the user's approval")
    if not isinstance(serial, str) or not SERIAL.match(serial):
        raise ValueError("That is not a device serial.")
    if which("scrcpy") is None:
        raise ValueError("scrcpy is not installed.")
    if which("adb") is None:
        raise ValueError("adb is not installed. Install the Android platform tools.")
    device = next((row for row in _devices(run) if row["serial"] == serial), None)
    if device is None:
        raise ValueError("That device is not connected.")
    if device["state"] != "device":
        raise ValueError(
            "The phone has not allowed this computer. Unlock it and accept the USB debugging prompt."
            if device["state"] == "unauthorized"
            else f"The device is {device['state']}."
        )
    return device


def mirror(
    serial: object,
    approve: object,
    which: Callable[[str], str | None] = shutil.which,
    run: Callable[..., Any] = subprocess.run,
    popen: Callable[..., Any] = subprocess.Popen,
) -> dict[str, Any]:
    """scrcpy's own window, which takes taps and keys."""
    device = _ready(serial, approve, which, run)
    if device["serial"] not in _alive():
        title = f"Hippocampus: {device['model'] or device['serial']}"
        _running[device["serial"]] = popen(
            ["scrcpy", "--serial", device["serial"], "--window-title", title, *SCRCPY_ARGS],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return status(which, run)


def view(
    serial: object,
    approve: object,
    which: Callable[[str], str | None] = shutil.which,
    run: Callable[..., Any] = subprocess.run,
    show: Callable[[str], None] = phone_view.show,
) -> dict[str, Any]:
    """The phone's screen inside the app, view only."""
    device = _ready(serial, approve, which, run)
    show(device["serial"])
    return status(which, run)


def stop(
    serial: object,
    which: Callable[[str], str | None] = shutil.which,
    run: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    process = _running.pop(serial, None) if isinstance(serial, str) else None
    if process is not None and process.poll() is None:
        process.terminate()
    if isinstance(serial, str):
        phone_view.hide(serial)
    return status(which, run)


KEYS = {
    "back": 4,
    "home": 3,
    "recents": 187,
    "power": 26,
    "volume_up": 24,
    "volume_down": 25,
    "enter": 66,
    "delete": 67,
}
TEXT_MAX = 500
SIZE = re.compile(r"(\d+)x(\d+)")


def screen_size(serial: str, run: Callable[..., Any] = subprocess.run) -> tuple[int, int]:
    """The phone's screen in pixels, upright. An override size (set by the user) wins over the physical one."""
    done = run(
        ["adb", "-s", serial, "shell", "wm", "size"],
        capture_output=True,
        text=True,
        timeout=SECONDS,
        check=False,
    )
    found = SIZE.findall(done.stdout or "")
    if done.returncode != 0 or not found:
        raise ValueError("Could not read the phone's screen size.")
    width, height = found[-1]
    return int(width), int(height)


def _point(value: object, name: str) -> float:
    if not isinstance(value, int | float) or not 0 <= value <= 1:
        raise ValueError(f'"{name}" must be a number from 0 to 1.')
    return float(value)


def control(
    serial: object,
    action: object,
    approve: object,
    which: Callable[[str], str | None] = shutil.which,
    run: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    """A tap, swipe, key or text on the phone, from the Phone dashboard. Points are 0 to 1 of the picture."""
    if approve is not True:
        raise ValueError("controlling a phone needs the user's approval")
    if not isinstance(serial, str) or not SERIAL.match(serial):
        raise ValueError("That is not a device serial.")
    if which("adb") is None:
        raise ValueError("adb is not installed. Install the Android platform tools.")
    if not isinstance(action, dict):
        raise ValueError('"action" must be an object.')
    kind = action.get("kind")
    if kind in ("tap", "swipe"):
        width, height = screen_size(serial, run)
        # The picture is wider than tall when the phone is turned; the size adb gives is upright.
        if bool(action.get("landscape")) != (width > height):
            width, height = height, width

        def at(x: str, y: str) -> list[str]:
            return [
                str(round(_point(action.get(x), x) * (width - 1))),
                str(round(_point(action.get(y), y) * (height - 1))),
            ]

        if kind == "tap":
            args = ["tap", *at("x", "y")]
        else:
            ms = action.get("ms", 250)
            if not isinstance(ms, int) or not 50 <= ms <= 5000:
                raise ValueError('"ms" must be a whole number from 50 to 5000.')
            args = ["swipe", *at("x", "y"), *at("x2", "y2"), str(ms)]
    elif kind == "key":
        code = KEYS.get(str(action.get("key")))
        if code is None:
            raise ValueError(f"The key must be one of: {', '.join(KEYS)}.")
        args = ["keyevent", str(code)]
    elif kind == "text":
        text = action.get("text")
        if not isinstance(text, str) or not text or len(text) > TEXT_MAX:
            raise ValueError(f"The text must be 1 to {TEXT_MAX} characters.")
        # adb's input text reads %s as a space; every other character goes through quoted.
        args = ["text", shlex.quote(text.replace("%", "\\%").replace(" ", "%s"))]
    else:
        raise ValueError("The action must be a tap, swipe, key or text.")
    done = run(
        ["adb", "-s", serial, "shell", "input", *args],
        capture_output=True,
        text=True,
        timeout=SECONDS,
        check=False,
    )
    if done.returncode != 0:
        raise ValueError(done.stderr.strip() or "The phone did not take the input.")
    return {"ok": True}


def agent_notes(run: Callable[..., Any] = subprocess.run) -> list[str]:
    """Lines for an agent's start-up inbox: the phones it can use and how. Empty when adb is missing."""
    if shutil.which("adb") is None:
        return []
    try:
        devices = [row for row in _devices(run) if row["state"] == "device"]
    except Exception:  # a courtesy line in a briefing: never let it stop the inbox being written
        return []
    lines = ["", "## Phones and devices you can use"]
    if not devices:
        return [*lines, "- None connected now. Run `adb devices -l` to check again."]
    for row in devices:
        lines.append(f"- {row['serial']} ({row['model'] or 'Android device'})")
    lines += [
        "Use adb with the serial (-s SERIAL). The user sees the phone live in the Phone dashboard.",
        "- See the screen: `adb -s SERIAL exec-out screencap -p > screen.png`, then read the picture.",
        "- Screen size: `adb -s SERIAL shell wm size`.",
        "- Tap: `adb -s SERIAL shell input tap X Y`. Swipe: `adb -s SERIAL shell input swipe X1 Y1 X2 Y2 300`.",
        "- Type: `adb -s SERIAL shell input text 'hello%sworld'` (%s is a space).",
        "- Keys: `adb -s SERIAL shell input keyevent 4` (back), 3 (home), 187 (recent apps).",
        "- Open an app: `adb -s SERIAL shell monkey -p PACKAGE 1`.",
        "Do nothing that pays, deletes, sends messages or signs in without the user's go-ahead.",
    ]
    return lines


def stop_all() -> None:
    for serial in list(_running):
        process = _running.pop(serial)
        if process.poll() is None:
            process.terminate()


atexit.register(stop_all)
