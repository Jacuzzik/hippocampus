"""Dictation by hotkey (7.27): record from the microphone, turn the speech into text with a local program, and
type it into the app that has the focus (or copy it). Nothing is sent anywhere and nothing is downloaded.

A speech-to-text program is not bundled. This looks for one that is installed:
  whisper.cpp   a `whisper-cli` (or `whisper-cpp`) program and a ggml model file
  faster-whisper  the Python package, with a model already in the local Hugging Face cache
If neither is there, `state()["missing"]` says exactly what to install."""

import importlib.util
import os
import shutil
import signal
import subprocess
import tempfile
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

CPP_PROGRAMS = ("whisper-cli", "whisper-cpp")
RECORDERS = ("pw-record", "parecord", "ffmpeg")
TYPERS = ("wtype", "ydotool", "xdotool")
COPIERS = ("wl-copy", "xclip")
SECONDS_MAX = 120
MODEL_DIRS = (
    "~/.local/share/whisper.cpp/models",
    "~/whisper.cpp/models",
    "~/.cache/whisper.cpp",
    "/usr/share/whisper.cpp-model-base.en",
    "/usr/share/whisper.cpp-model-base",
    "/usr/share/whisper.cpp-model-small",
)
Which = Callable[[str], str | None]


def _first(names: tuple[str, ...], which: Which) -> str | None:
    return next((n for n in names if which(n)), None)


def find_model(configured: str = "") -> Path | None:
    """The whisper.cpp model file: the one the user set, or the first ggml model in the usual folders."""
    if configured and Path(configured).expanduser().is_file():
        return Path(configured).expanduser()
    for folder in MODEL_DIRS:
        root = Path(folder).expanduser()
        if root.is_dir():
            found = sorted(root.glob("ggml-*.bin"))
            if found:
                return found[0]
    return None


def cached_faster_whisper() -> str | None:
    hub = Path(os.environ.get("HF_HOME", "~/.cache/huggingface")).expanduser() / "hub"
    found = sorted(hub.glob("models--Systran--faster-whisper-*")) if hub.is_dir() else []
    return found[0].name.rsplit("faster-whisper-", 1)[1] if found else None


def state(configured_model: str = "", which: Which = shutil.which) -> dict[str, Any]:
    recorder = _first(RECORDERS, which)
    cpp = _first(CPP_PROGRAMS, which)
    model = find_model(configured_model)
    fast = importlib.util.find_spec("faster_whisper") is not None
    cached = cached_faster_whisper()
    engine = "whisper.cpp" if cpp and model else "faster-whisper" if fast and cached else None
    missing: list[dict[str, str]] = []
    if not recorder:
        missing.append(
            {
                "what": "A microphone recorder",
                "how": "Install PipeWire's tools (they provide pw-record): on Arch, `sudo pacman -S pipewire`; "
                "or PulseAudio's (parecord): `sudo pacman -S libpulse`.",
            }
        )
    if not engine:
        hint = (
            "Install whisper.cpp (on Arch: `yay -S whisper.cpp`, or build github.com/ggml-org/whisper.cpp) and "
            "a model (`sh ./models/download-ggml-model.sh base.en`), then put the model file's path below. "
            "Or install faster-whisper: `uv pip install faster-whisper`"
        )
        hint += (
            f" (the {cached} model is already in your Hugging Face cache, so it needs no download)."
            if cached
            else ", then run it once with the network on to fetch a model."
        )
        if cpp and not model:
            hint = "whisper.cpp is installed but no model was found. Download one (`sh ./models/download-ggml-model.sh base.en`) and put its path below."
        missing.append({"what": "A speech-to-text program", "how": hint})
    typer = _first(TYPERS, which)
    copier = _first(COPIERS, which)
    return {
        "ready": bool(recorder and engine),
        "recorder": recorder,
        "engine": engine,
        "model": str(model) if model else "",
        "typer": typer,
        "copier": copier,
        "missing": missing,
    }


def record_command(recorder: str, path: Path) -> list[str]:
    if recorder == "pw-record":
        return ["pw-record", "--rate", "16000", "--channels", "1", str(path)]
    if recorder == "parecord":
        return ["parecord", "--rate=16000", "--channels=1", "--file-format=wav", str(path)]
    return [
        "ffmpeg",
        "-loglevel",
        "error",
        "-f",
        "pulse",
        "-i",
        "default",
        "-ar",
        "16000",
        "-ac",
        "1",
        "-y",
        str(path),
    ]


def transcribe_cpp(program: str, model: Path, wav: Path) -> str:
    done = subprocess.run(  # noqa: S603 (fixed argument list, no shell)
        [program, "-m", str(model), "-f", str(wav), "-nt", "-np"],
        capture_output=True,
        text=True,
        timeout=180,
        check=False,
    )
    if done.returncode != 0:
        raise ValueError(
            f"whisper.cpp stopped with code {done.returncode}: {done.stderr.strip()[-200:]}"
        )
    return " ".join(done.stdout.split())


def transcribe_faster(size: str, wav: Path) -> str:
    from faster_whisper import WhisperModel  # type: ignore[import-not-found]  # noqa: PLC0415

    # local_files_only: a model is never downloaded behind the user's back.
    model = WhisperModel(size, device="cpu", compute_type="int8", local_files_only=True)
    segments, _ = model.transcribe(str(wav))
    return " ".join(s.text.strip() for s in segments).strip()


def deliver(text: str, mode: str, found: dict[str, Any]) -> str:
    """Type the text into the focused app, or copy it. Returns what was done, in plain words."""
    if mode == "type" and found["typer"]:
        argv = {
            "wtype": ["wtype", "--", text],
            "ydotool": ["ydotool", "type", text],
            "xdotool": ["xdotool", "type", "--", text],
        }[found["typer"]]
        if subprocess.run(argv, capture_output=True, timeout=20, check=False).returncode == 0:  # noqa: S603
            return f"typed with {found['typer']}"
    if found["copier"]:
        argv = (
            ["wl-copy", "--", text]
            if found["copier"] == "wl-copy"
            else ["xclip", "-selection", "clipboard"]
        )
        done = subprocess.run(  # noqa: S603
            argv,
            input=None if found["copier"] == "wl-copy" else text.encode(),
            capture_output=True,
            timeout=10,
            check=False,
        )
        if done.returncode == 0:
            return "copied to the clipboard"
    return "shown here only (no typing or clipboard program is installed)"


class Dictation:
    def __init__(self) -> None:
        self.proc: subprocess.Popen[bytes] | None = None
        self.wav: Path | None = None
        self.started = 0.0

    @property
    def recording(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self, found: dict[str, Any]) -> None:
        if not found["ready"]:
            raise ValueError(
                "Dictation is not set up: " + " ".join(m["how"] for m in found["missing"])
            )
        if self.recording:
            raise ValueError("Already listening.")
        handle, name = tempfile.mkstemp(suffix=".wav", prefix="hippo-dictation-")
        os.close(handle)
        self.wav = Path(name)
        self.proc = subprocess.Popen(  # noqa: S603
            record_command(str(found["recorder"]), self.wav),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.started = time.time()

    def stop(self, found: dict[str, Any], transcribe: Callable[[Path], str] | None = None) -> str:
        proc, wav = self.proc, self.wav
        if proc is None or wav is None:
            raise ValueError("Dictation is not listening.")
        self.proc = self.wav = None
        try:
            if proc.poll() is None:
                proc.send_signal(signal.SIGINT)  # the recorder finishes the file on SIGINT
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
            if not wav.is_file() or wav.stat().st_size < 2000:
                raise ValueError("Nothing was recorded. Check the microphone.")
            if transcribe is not None:
                return transcribe(wav).strip()
            if found["engine"] == "whisper.cpp":
                program = _first(CPP_PROGRAMS, shutil.which) or CPP_PROGRAMS[0]
                return transcribe_cpp(program, Path(found["model"]), wav)
            return transcribe_faster(cached_faster_whisper() or "small", wav)
        finally:
            wav.unlink(missing_ok=True)  # the recording is never kept

    def cancel(self) -> None:
        if self.proc is not None:
            self.proc.kill()
        if self.wav is not None:
            self.wav.unlink(missing_ok=True)
        self.proc = self.wav = None
