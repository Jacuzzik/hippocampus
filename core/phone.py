"""The Phone dashboard: Android devices seen by adb, and screen mirroring with scrcpy.

scrcpy opens its own window; it cannot draw inside this app. Mirroring starts only on the user's click
(the request must carry approve: true), with small settings so a weak computer copes.
"""

import atexit
import re
import shutil
import subprocess
from collections.abc import Callable
from typing import Any

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


def mirror(
    serial: object,
    approve: object,
    which: Callable[[str], str | None] = shutil.which,
    run: Callable[..., Any] = subprocess.run,
    popen: Callable[..., Any] = subprocess.Popen,
) -> dict[str, Any]:
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
    if serial not in _alive():
        title = f"Hippocampus: {device['model'] or serial}"
        _running[serial] = popen(
            ["scrcpy", "--serial", serial, "--window-title", title, *SCRCPY_ARGS],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return status(which, run)


def stop(
    serial: object,
    which: Callable[[str], str | None] = shutil.which,
    run: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    process = _running.pop(serial, None) if isinstance(serial, str) else None
    if process is not None and process.poll() is None:
        process.terminate()
    return status(which, run)


def stop_all() -> None:
    for serial in list(_running):
        process = _running.pop(serial)
        if process.poll() is None:
            process.terminate()


atexit.register(stop_all)
