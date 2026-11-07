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
import time
import termios
import threading
from pathlib import Path
from typing import Any, Callable

from ai import cli_sessions
from core.settings import ROOT
from tools.vault_mcp import VAULT_TOOLS, mcp_config

# How much recent output a terminal keeps for replay on reopen.
SCREEN_BYTES = 200_000

# Provider name (as the app stores it) to the CLI that runs for it in the terminal.
CLI_FOR = {"claude": "claude", "codex": "codex", "ollama": "ollama", "antigravity": "agy", "gemini-cli": "gemini"}


class Terminals:
    def __init__(self, emit: Callable[[dict[str, Any]], None], screen_dir: Path | None = None) -> None:
        self.emit = emit
        # Where each terminal's recent output is kept between app restarts.
        self.screen_dir = screen_dir
        self.saved_at: dict[str, float] = {}
        self.procs: dict[str, tuple[subprocess.Popen, int]] = {}
        # The command each agent's terminal was started with; it has no keys or secrets, only the CLI and its flags.
        self.argvs: dict[str, list[str]] = {}
        # The folder each agent works in, and a short cache of its last command (the card refreshes every 3 seconds).
        self.folders: dict[str, str] = {}
        # The provider and model each running terminal was started with, to notice a change.
        self.specs: dict[str, tuple[str, str]] = {}
        self.last_cmd_cache: dict[str, tuple[float, str | None]] = {}
        # When each terminal started and when it last printed, for its Working / Idle status.
        self.started_at: dict[str, float] = {}
        self.last_output: dict[str, float] = {}
        # The recent output of each terminal, so a reopened terminal shows what was on screen.
        self.screens: dict[str, bytearray] = {}
        self.lock = threading.Lock()
        # Agents whose terminal the app stopped on purpose (no error line for those).
        self.stopping: set[str] = set()

    def start(
        self,
        agent: str,
        provider: str,
        rows: int,
        cols: int,
        model: str = "",
        folder: str | None = None,
        briefing: str = "",
        vault: str | None = None,
    ) -> dict[str, Any]:
        with self.lock:
            running = self.procs.get(agent)
            if running is not None and running[0].poll() is None:
                old_provider, old_model = self.specs.get(agent, ("", ""))
                changed = old_provider != provider or (bool(model) and old_model != model)
                if changed:
                    # The provider or model was changed: stop the old CLI so the new one starts in its place.
                    self.stopping.add(agent)
                    running[0].terminate()
                    try:
                        running[0].wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        running[0].kill()
                    os.close(running[1])
                    self.procs.pop(agent, None)
                    running = None
            if running is not None and running[0].poll() is None:
                # Reattaching: the new screen is blank, so resize one row off and back to make the CLI redraw.
                self._resize(running[1], rows + 1, cols)
                self._resize(running[1], rows, cols)
                return {"running": True, "replay": self._replay(agent)}
            # A changed provider or model starts a new session; the same one keeps its history.
            # A start with no model (the main terminal) does not count as a change.
            if model:
                cli_sessions.set_engine_for(agent, f"{provider} {model}")
            argv = _command(agent, provider, model, self._write_briefing(agent, briefing), vault)
            master, slave = pty.openpty()
            self._resize(slave, rows, cols)
            try:
                proc = subprocess.Popen(
                    argv,
                    stdin=slave,
                    stdout=slave,
                    stderr=slave,
                    # CLAUDE_CODE_CHILD_SESSION turns off transcript saving, so the agent's session could not be resumed.
                    env={
                        **{k: v for k, v in os.environ.items() if k != "CLAUDE_CODE_CHILD_SESSION"},
                        "TERM": "xterm-256color",
                        **provider_env(provider),
                    },
                    # The agent's own folder is its working directory; a missing one falls back to the app's.
                    cwd=folder if folder and os.path.isdir(folder) else None,
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
            self.specs[agent] = (provider, model or (self.specs.get(agent, ("", ""))[1] if self.specs.get(agent, ("", ""))[0] == provider else ""))
            # The briefing is kept out of the shown command: it is long, and it is text, not a flag to read.
            self.argvs[agent] = argv[: argv.index("--append-system-prompt-file")] if "--append-system-prompt-file" in argv else argv
            self.folders[agent] = folder or ""
            self.started_at[agent] = time.time()
            self.last_output.pop(agent, None)
            # The earlier screen (kept across restarts) is shown first; the new output follows it.
            replay = self._replay(agent)
        threading.Thread(target=self._pump, args=(agent, proc, master), daemon=True).start()
        return {"running": True, "replay": replay}

    def _write_briefing(self, agent: str, text: str) -> str:
        """The briefing is written to a file and passed by path, so its text is not on the command line or in the shown command."""
        if not text or self.screen_dir is None:
            return ""
        path = self.screen_dir.parent / "briefings" / f"{agent}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return str(path)

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
            # A stop we asked for is not a failure: _pump shows no error line for it.
            self.stopping.add(agent)
            running[0].terminate()

    def info(self, agent: str) -> dict[str, Any]:
        """The command the agent's terminal runs and its status: Working or Idle, or None when stopped."""
        running = self.procs.get(agent)
        if running is None or running[0].poll() is not None:
            return {"command": None, "status": None, "last": self._last_command(agent), "model": cli_sessions.last_model(agent)}
        last = self.last_output.get(agent)
        running = cli_sessions.open_tool_calls(agent)
        status = "Working" if running or (last is not None and time.time() - last < 10) else "Idle"
        # The newest command, shown on the card when nothing is running.
        last_cmd = self._last_command(agent)
        # Show the CLI and its flags, not the folder and vault paths that follow --add-dir.
        shown = self.argvs.get(agent, [])
        if "--add-dir" in shown:
            shown = shown[: shown.index("--add-dir")]
        command = " ".join([os.path.basename(shown[0]), *shown[1:]]) if shown else ""
        return {"command": command, "status": status, "running": running, "last": last_cmd, "model": cli_sessions.last_model(agent)}

    def _last_command(self, agent: str) -> str | None:
        """The agent's newest command: Claude's transcript first, then the Codex sessions run in its folder. Cached for 10 seconds."""
        cached = self.last_cmd_cache.get(agent)
        if cached is not None and time.time() - cached[0] < 10:
            return cached[1]
        found = cli_sessions.last_tool_call(agent)
        folder = self.folders.get(agent)
        if found is None and folder:
            found = cli_sessions.codex_last_tool(folder)
        self.last_cmd_cache[agent] = (time.time(), found)
        return found

    def _replay(self, agent: str) -> str:
        """The output to show when a terminal opens: kept in memory, or the saved copy after a restart."""
        if agent not in self.screens and self.screen_dir is not None:
            try:
                self.screens[agent] = bytearray((self.screen_dir / f"{agent}.bin").read_bytes())
            except OSError:
                pass
        return bytes(self.screens.get(agent, b"")).decode("utf-8", errors="replace")

    def _save(self, agent: str) -> None:
        self.saved_at[agent] = time.time()
        if self.screen_dir is None or agent not in self.screens:
            return
        try:
            self.screen_dir.mkdir(parents=True, exist_ok=True)
            (self.screen_dir / f"{agent}.bin").write_bytes(bytes(self.screens[agent]))
        except OSError:
            pass

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
                self.last_output[agent] = time.time()
                screen = self.screens.setdefault(agent, bytearray())
                screen += chunk
                del screen[: max(0, len(screen) - SCREEN_BYTES)]
                if time.time() - self.saved_at.get(agent, 0) >= 5:
                    self._save(agent)
                self.emit({"event": "terminal", "agent": agent, "data": decoder.decode(chunk)})
        finally:
            code = proc.wait()
            self._save(agent)
            os.close(master)
            with self.lock:
                if self.procs.get(agent, (None, None))[0] is proc:
                    del self.procs[agent]
            stopped_by_us = agent in self.stopping
            self.stopping.discard(agent)
            if code != 0 and not stopped_by_us:
                # Says what a failed exit usually means, so the terminal shows an error message, not just a code.
                self.emit({"event": "terminal", "agent": agent, "data": f"\r\nError: the CLI stopped with code {code}. Check that it is installed and signed in, then open it again.\r\n"})
            self.emit({"event": "terminal", "agent": agent, "exit": code})


# API providers run in OpenCode's terminal UI: its provider id, and the environment variable it reads the key from.
# shortcut: the OpenCode provider ids and key names are not checked against a live key, so each one is unverified until tested.
OPENCODE_FOR = {
    "openai": ("openai", "OPENAI_API_KEY"),
    "xai": ("xai", "XAI_API_KEY"),
    "moonshot": ("moonshot", "MOONSHOT_API_KEY"),
    "gemini": ("google", "GOOGLE_GENERATIVE_AI_API_KEY"),
    "qwen": ("alibaba", "DASHSCOPE_API_KEY"),
    "deepseek": ("deepseek", "DEEPSEEK_API_KEY"),
    "mistral": ("mistral", "MISTRAL_API_KEY"),
    "groq": ("groq", "GROQ_API_KEY"),
    "openrouter": ("openrouter", "OPENROUTER_API_KEY"),
    "lmstudio": ("lmstudio", ""),
    "vllm": ("vllm", ""),
}


def provider_env(provider: str) -> dict[str, str]:
    """The API key an OpenCode provider needs, read from the app's key store; empty when none is saved."""
    if provider not in OPENCODE_FOR:
        return {}
    from ai.keys import get_key

    env_name = OPENCODE_FOR[provider][1]
    key = get_key(provider) if env_name else None
    return {env_name: key} if key else {}


def _command(agent: str, provider: str, model: str = "", briefing: str = "", vault: str | None = None) -> list[str]:
    if provider in OPENCODE_FOR:
        binary = shutil.which("opencode")
        if binary is None:
            raise RuntimeError("opencode is not installed. Install OpenCode, then open this terminal again.")
        if not model:
            raise RuntimeError(f"Pick a model for {provider} first.")
        return [binary, "-m", f"{OPENCODE_FOR[provider][0]}/{model}"]
    name = CLI_FOR.get(provider)
    if name is None:
        raise RuntimeError(f'The terminal does not run "{provider}" yet.')
    binary = shutil.which(name)
    if binary is None:
        raise RuntimeError(f"{name} is not installed. Install it, then sign in with `{name}` in a terminal.")
    if name == "ollama":
        return [binary, "run", model]
    if name == "agy":
        # Antigravity takes the model as a flag (`agy --model <name>`).
        return [binary, "--model", model] if model else [binary]
    if name != "claude":
        return [binary]
    entry = cli_sessions.get(agent)
    # Resume whenever Claude Code has saved this session, so its history is kept; otherwise start it under the same id.
    flag = "--resume" if cli_sessions.has_transcript(entry["id"]) else "--session-id"
    # Added agents get no access to the app's own code: Read, Edit and Write under the app folder are denied.
    # Claude Code reads a single leading slash as project-relative, so an absolute path needs a double slash to match.
    rules = [f"{tool}(/{ROOT}/**)" for tool in ("Read", "Edit", "Write")]
    # The briefing applies to every start, resumed or new: it sets the rules (e.g. answer from the vault) for this run.
    brief = ["--append-system-prompt-file", briefing] if briefing else []
    # The vault is open to read and search; agents cannot run rm. Hub notes are protected from deletion in the app's tools.
    vault_dir = ["--add-dir", vault] if vault else []
    # The terminal gets the same vault tools as the chat, so its deletes go through the app's checks, not a shell.
    vault_tools = (
        ["--mcp-config", mcp_config(vault), "--allowedTools", *[f"mcp__vault__{name}" for name in VAULT_TOOLS]] if vault else []
    )
    return [
        binary,
        flag,
        entry["id"],
        *(["--model", model] if model else []),
        *vault_dir,
        *vault_tools,
        "--disallowedTools",
        *rules,
        # The main agent gets a fenced shell: no delete, move, git, network or privilege commands, and none that names the app folder.
        # Best effort only: a shell can still reach files that no pattern names. Normal agents get no shell.
        *(
            [f"Bash({cmd}:*)" for cmd in ("rm", "rmdir", "mv", "cp", "git", "sudo", "chmod", "chown", "curl", "wget", "dd", "kill", "pkill", "ps", "pgrep", "top", "htop", "lsof", "ss", "netstat", "pidof", "claude")]
            + [f"Bash(* {ROOT}*)"]
            if agent == "hippo"
            else ["Bash"]
        ),
        *brief,
    ]
