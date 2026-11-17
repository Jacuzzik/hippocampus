"""The phone's screen inside the app (DB.09). scrcpy's own window cannot be put inside the app, so its
phone-side server is used directly:

  phone (scrcpy-server, raw H.264) -> adb forward -> this module -> ffmpeg (to JPEG frames)
  -> a local HTTP stream at 127.0.0.1 with a secret token -> an <img> in the Phone dashboard.

View only: taps and keys stay with the separate scrcpy window. Light settings (720 pixels, 15 frames a
second, no sound) so a weak computer copes. Nothing runs until the user clicks, and everything stops
with the dashboard's Stop button or when the app closes.
"""

import atexit
import secrets
import shutil
import socket
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

SERVER_JAR = Path("/usr/share/scrcpy/scrcpy-server")
REMOTE_JAR = "/data/local/tmp/hippocampus-scrcpy-server.jar"
MAX_SIZE = 720
MAX_FPS = 15
CONNECT_S = 10.0
BOUNDARY = "hippoframe"


def scrcpy_version() -> str:
    done = subprocess.run(
        ["scrcpy", "--version"], capture_output=True, text=True, timeout=10, check=False
    )
    first = (done.stdout or "").split()
    if len(first) < 2:
        raise ValueError("Could not read the scrcpy version.")
    return first[1]


def jpeg_frames(buffer: bytearray) -> list[bytes]:
    """Cut whole JPEG pictures (FFD8 ... FFD9) off the front of the buffer; the rest stays for next time."""
    frames = []
    while True:
        start = buffer.find(b"\xff\xd8")
        if start < 0:
            buffer.clear()
            return frames
        end = buffer.find(b"\xff\xd9", start + 2)
        if end < 0:
            del buffer[:start]
            return frames
        frames.append(bytes(buffer[start : end + 2]))
        del buffer[: end + 2]


class View:
    """One phone's screen: the phone-side server, the adb tunnel, ffmpeg and the newest picture."""

    def __init__(self, serial: str) -> None:
        self.serial = serial
        self.scid = f"{secrets.randbits(31):08x}"
        self.port = _free_port()
        self.frame = b""
        self.changed = threading.Condition()
        self.alive = True
        self.server: subprocess.Popen | None = None
        self.ffmpeg: subprocess.Popen | None = None
        self.sock: socket.socket | None = None

    def _adb(self, *args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            ["adb", "-s", self.serial, *args],
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
        )

    def start(self) -> None:
        if not SERVER_JAR.is_file():
            raise ValueError(f"scrcpy's phone server is not at {SERVER_JAR}.")
        if shutil.which("ffmpeg") is None:
            raise ValueError("ffmpeg is not installed, so the screen cannot be shown in the app.")
        if self._adb("push", str(SERVER_JAR), REMOTE_JAR).returncode != 0:
            raise ValueError("Could not copy scrcpy's server to the phone.")
        if self._adb("forward", f"tcp:{self.port}", f"localabstract:scrcpy_{self.scid}").returncode:
            raise ValueError("Could not open the tunnel to the phone.")
        self.server = subprocess.Popen(
            ["adb", "-s", self.serial, "shell", f"CLASSPATH={REMOTE_JAR}", "app_process", "/",
             "com.genymobile.scrcpy.Server", scrcpy_version(), f"scid={self.scid}",
             "tunnel_forward=true", "audio=false", "control=false", "raw_stream=true",
             f"max_size={MAX_SIZE}", f"max_fps={MAX_FPS}", "video_codec=h264", "cleanup=true"],
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )  # fmt: skip
        self.sock = self._connect()
        self.ffmpeg = subprocess.Popen(
            ["ffmpeg", "-loglevel", "error", "-f", "h264", "-i", "pipe:0", "-an",
             "-f", "image2pipe", "-c:v", "mjpeg", "-q:v", "7", "pipe:1"],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
        )  # fmt: skip
        threading.Thread(target=self._feed, daemon=True).start()
        threading.Thread(target=self._read, daemon=True).start()

    def _connect(self) -> socket.socket:
        """The tunnel accepts at once but sends nothing until the phone's server is up, so wait for bytes."""
        deadline = time.monotonic() + CONNECT_S
        while time.monotonic() < deadline:
            try:
                sock = socket.create_connection(("127.0.0.1", self.port), timeout=3)
                first = sock.recv(65536)
                if first:
                    self._first = first
                    sock.settimeout(None)
                    return sock
                sock.close()
            except OSError:
                pass
            time.sleep(0.3)
        self.stop()
        raise ValueError("The phone did not start sending its screen. Unlock it and try again.")

    def _feed(self) -> None:
        assert self.sock and self.ffmpeg and self.ffmpeg.stdin
        try:
            self.ffmpeg.stdin.write(self._first)
            while self.alive:
                chunk = self.sock.recv(65536)
                if not chunk:
                    break
                self.ffmpeg.stdin.write(chunk)
        except OSError:
            pass
        self.stop()

    def _read(self) -> None:
        assert self.ffmpeg and self.ffmpeg.stdout
        buffer = bytearray()
        while self.alive:
            chunk = self.ffmpeg.stdout.read1(65536)
            if not chunk:
                break
            buffer += chunk
            frames = jpeg_frames(buffer)
            if frames:
                with self.changed:
                    self.frame = frames[-1]
                    self.changed.notify_all()
        self.stop()

    def stop(self) -> None:
        if not self.alive:
            return
        self.alive = False
        with self.changed:
            self.changed.notify_all()
        for process in (self.ffmpeg, self.server):
            if process is not None and process.poll() is None:
                process.terminate()
        if self.sock is not None:
            try:
                self.sock.close()
            except OSError:
                pass
        try:
            self._adb("forward", "--remove", f"tcp:{self.port}")
        except (OSError, subprocess.SubprocessError):
            pass


def _free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


_views: dict[str, View] = {}
_token = secrets.token_urlsafe(24)
_http: ThreadingHTTPServer | None = None
_lock = threading.Lock()


class _Stream(BaseHTTPRequestHandler):
    def log_message(self, *args: object) -> None:  # no request log on stderr
        pass

    def do_GET(self) -> None:
        path, _, query = self.path.partition("?")
        serial = path.removeprefix("/phone/").removesuffix(".mjpg")
        view = _views.get(serial)
        if query != f"t={_token}" or view is None or not view.alive:
            self.send_error(404)
            return
        self.send_response(200)
        self.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={BOUNDARY}")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        last = b""
        try:
            while view.alive:
                seen = last
                with view.changed:
                    view.changed.wait_for(
                        lambda seen=seen: view.frame is not seen or not view.alive, 5
                    )
                    frame = view.frame
                if not view.alive:
                    break
                if frame is last or not frame:
                    continue
                last = frame
                self.wfile.write(
                    f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\nContent-Length: {len(frame)}\r\n\r\n".encode()
                    + frame
                    + b"\r\n"
                )
        except OSError:
            pass  # the window closed the picture


def _server() -> ThreadingHTTPServer:
    global _http
    if _http is None:
        _http = ThreadingHTTPServer(("127.0.0.1", 0), _Stream)
        _http.daemon_threads = True
        threading.Thread(target=_http.serve_forever, daemon=True).start()
    return _http


def url(serial: str) -> str:
    return f"http://127.0.0.1:{_server().server_address[1]}/phone/{serial}.mjpg?t={_token}"


def showing() -> dict[str, str]:
    """Each phone shown in the app, with the address of its picture stream."""
    for serial in [s for s, v in _views.items() if not v.alive]:
        del _views[serial]
    return {serial: url(serial) for serial in sorted(_views)}


def show(serial: str) -> None:
    with _lock:
        if serial in showing():
            return
        view = View(serial)
        view.start()
        _views[serial] = view


def hide(serial: str) -> None:
    view = _views.pop(serial, None)
    if view is not None:
        view.stop()


def hide_all() -> None:
    for serial in list(_views):
        hide(serial)


atexit.register(hide_all)
