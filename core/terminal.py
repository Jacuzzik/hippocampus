"""A real terminal per added agent: the agent's own CLI runs in a pseudo-terminal and its screen streams to the app.

Claude uses the agent's Claude Code session (ai/cli_sessions.py), so the terminal and the chat share one conversation.
"""

import codecs
import fcntl
import os
import pty
import shutil
import struct
import subprocess
import termios
import threading
from typing import Any, Callable

from ai import cli_sessions

# Provider name (as the app stores it) to the CLI that runs for it in the terminal.
CLI_FOR = {"claude": "claude", "codex": "codex", "openai": "codex"}


class Terminals:
    def __init__(self, emit: Callable[[dict[str, Any]], None]) -> None:
        self.emit = emit
        self.procs: dict[str, tuple[subprocess.Popen, int]] = {}
        self.lock = threading.Lock()

    def start(self, agent: str, provider: str, rows: int, cols: int) -> dict[str, Any]:
        with self.lock:
            running = self.procs.get(agent)
            if running is not None and running[0].poll() is None:
                self._resize(running[1], rows, cols)
                return {"running": True}
            argv = _command(agent, provider)
            master, slave = pty.openpty()
            self._resize(slave, rows, cols)
            try:
                proc = subprocess.Popen(
                    argv,
                    stdin=slave,
                    stdout=slave,
                    stderr=slave,
                    env={**os.environ, "TERM": "xterm-256color"},
                    start_new_session=True,
                    close_fds=True,
                )
            except OSError as cause:
                os.close(master)
                raise RuntimeError(f"Could not start {argv[0]}: {cause}") from cause
            finally:
                os.close(slave)
            if argv[1:2] == ["--session-id"] or argv[1:2] == ["--resume"]:
                cli_sessions.mark_started(agent)
            self.procs[agent] = (proc, master)
        threading.Thread(target=self._pump, args=(agent, proc, master), daemon=True).start()
        return {"running": True}

    def write(self, agent: str, data: str) -> None:
        running = self.procs.get(agent)
        if running is None or running[0].poll() is not None:
            raise RuntimeError("The terminal is not running. Open it again.")
        os.write(running[1], data.encode("utf-8"))

    def resize(self, agent: str, rows: int, cols: int) -> None:
        running = self.procs.get(agent)
        if running is not None and running[0].poll() is None:
            self._resize(running[1], rows, cols)

    def stop(self, agent: str) -> None:
        running = self.procs.get(agent)
        if running is not None and running[0].poll() is None:
            running[0].terminate()

    @staticmethod
    def _resize(fd: int, rows: int, cols: int) -> None:
        fcntl.ioctl(fd, termios.TIOCSWINSZ, struct.pack("HHHH", max(rows, 1), max(cols, 1), 0, 0))

    def _pump(self, agent: str, proc: subprocess.Popen, master: int) -> None:
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        try:
            while True:
                try:
                    chunk = os.read(master, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                self.emit({"event": "terminal", "agent": agent, "data": decoder.decode(chunk)})
        finally:
            code = proc.wait()
            os.close(master)
            with self.lock:
                if self.procs.get(agent, (None, None))[0] is proc:
                    del self.procs[agent]
            self.emit({"event": "terminal", "agent": agent, "exit": code})


def _command(agent: str, provider: str) -> list[str]:
    name = CLI_FOR.get(provider)
    if name is None:
        raise RuntimeError(f'The terminal does not run "{provider}" yet. Claude and Codex work.')
    binary = shutil.which(name)
    if binary is None:
        raise RuntimeError(f"{name} is not installed. Install it, then sign in with `{name}` in a terminal.")
    if name != "claude":
        return [binary]
    entry = cli_sessions.get(agent)
    flag = "--resume" if entry.get("started") else "--session-id"
    return [binary, flag, entry["id"]]
