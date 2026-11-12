"""A real terminal per added agent: the agent's own CLI runs in a pseudo-terminal and its screen streams to the app.

Claude uses the agent's Claude Code session (ai/cli_sessions.py), so the terminal and the chat share one conversation.
"""

import codecs
import fcntl
import json
import os
import pty
import shutil
import signal
import struct
import subprocess
import time
import termios
import threading
from pathlib import Path
from typing import Any, Callable

from ai import cli_sessions
from core.settings import HIVE_DIR, ROOT
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
        # Agents whose old CLI was replaced by a new start, so its late exit is not shown.
        self.replaced: set[str] = set()
        # The last start or stop of each agent's terminal: (time, "started" or "stopped"), shown on the Monitor tab.
        self.events: dict[str, tuple[float, str]] = {}

    def _log_event(self, agent: str, what: str) -> None:
        """Remember and append one start or stop of an agent's terminal, to agent-events.jsonl beside the screens."""
        now = time.time()
        self.events[agent] = (now, what)
        if self.screen_dir is None:
            return
        try:
            with (self.screen_dir.parent / "agent-events.jsonl").open("a", encoding="utf-8") as log:
                log.write(json.dumps({"ts": now, "agent": agent, "event": what}) + "\n")
        except OSError:
            pass

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
        block_tools: bool = False,
    ) -> dict[str, Any]:
        with self.lock:
            running = self.procs.get(agent)
            if running is not None and running[0].poll() is None:
                old_provider, old_model = self.specs.get(agent, ("", ""))
                changed = old_provider != provider or (bool(model) and old_model != model)
                if changed:
                    # The provider or model was changed: stop the old CLI so the new one starts in its place.
                    self.stopping.add(agent)
                    # The old CLI's exit is not the new session's: its pump must not report it.
                    self.replaced.add(agent)
                    running[0].terminate()
                    try:
                        running[0].wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        running[0].kill()
                    # Its pump closes the pty when the old CLI exits; closing it here too reused a number for the new one.
                    self.procs.pop(agent, None)
                    running = None
            if running is not None and running[0].poll() is None:
                # Reattaching: the new screen is blank, so resize one row off and back to make the CLI redraw.
                self._resize_running(running[0], running[1], rows + 1, cols)
                self._resize_running(running[0], running[1], rows, cols)
                # "reattached" tells the caller that no CLI was started, so start-up messages are not sent again.
                return {"running": True, "reattached": True, "replay": self._replay(agent)}
            previous = self.specs.get(agent)
            if previous and (previous[0] != provider or (model and previous[1] != model)):
                # A new engine starts a new session: its screen starts blank, not with the old session's output.
                self.screens.pop(agent, None)
                if self.screen_dir is not None:
                    (self.screen_dir / f"{agent}.bin").unlink(missing_ok=True)
            # A changed provider or model starts a new session; the same one keeps its history.
            # A start with no model (the main terminal) does not count as a change.
            if model:
                cli_sessions.set_engine_for(agent, f"{provider} {model}")
            # An agent that has started on this engine before resumes its session in every CLI, not only Claude Code.
            resume = bool(cli_sessions.get(agent).get("started"))
            brief_path = self._write_briefing(agent, briefing)
            argv = _command(agent, provider, model, brief_path, vault, block_tools, resume)
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
            if provider != "claude" or argv[1:2] == ["--session-id"] or argv[1:2] == ["--resume"]:
                cli_sessions.mark_started(agent)
            self.procs[agent] = (proc, master)
            # Only Claude Code takes the briefing as a flag. Every other CLI gets a short first message pointing at the briefing file.
            if brief_path and provider != "claude" and provider not in OPENCODE_FOR:
                threading.Thread(target=self._send_briefing, args=(agent, proc, master, brief_path), daemon=True).start()
            # Claude terminals start Remote Control, so the agent can be reached from the Claude apps.
            if provider == "claude":
                threading.Thread(target=self._send_remote_control, args=(agent, proc, master), daemon=True).start()
            self.specs[agent] =(provider, model or (self.specs.get(agent, ("", ""))[1] if self.specs.get(agent, ("", ""))[0] == provider else ""))
            # The briefing is kept out of the shown command: it is long, and it is text, not a flag to read.
            self.argvs[agent] = argv[: argv.index("--append-system-prompt-file")] if "--append-system-prompt-file" in argv else argv
            self.folders[agent] = folder or ""
            self.started_at[agent] = time.time()
            self.last_output.pop(agent, None)
            self._log_event(agent, "started")
            # The earlier screen (kept across restarts) is shown first; the new output follows it.
            replay = self._replay(agent)
        threading.Thread(target=self._pump, args=(agent, proc, master), daemon=True).start()
        return {"running": True, "replay": replay}

    def _send_briefing(self, agent: str, proc: subprocess.Popen, master: int, brief_path: str) -> None:
        """Types the briefing pointer into the CLI once its screen has drawn and gone quiet, so the input is not lost in a half-started screen. Skipped if that terminal has stopped or been replaced."""
        started = time.time()
        deadline = started + BRIEFING_WAIT_MAX_S
        while time.time() < deadline:
            if proc.poll() is not None or self.procs.get(agent, (None, None))[1] != master:
                self._log_event(agent, "briefing pointer skipped: CLI stopped before it was sent")
                return
            first = self.last_output.get(agent)
            if first is not None and time.time() - started >= BRIEFING_DELAY_S:
                break
            time.sleep(0.5)
        # Past the deadline the pointer is still sent if the CLI is running, rather than dropped without a trace.
        if proc.poll() is not None or self.procs.get(agent, (None, None))[1] != master:
            self._log_event(agent, "briefing pointer skipped: CLI stopped before it was sent")
            return
        message = f"Your briefing is in {brief_path}. Read it now and follow it for this session."
        try:
            os.write(master, message.encode("utf-8"))
            time.sleep(SUBMIT_DELAY_S)
            os.write(master, b"\r")
            self._log_event(agent, "briefing pointer sent")
        except OSError as cause:
            self._log_event(agent, f"briefing pointer failed: {cause}")

    def _send_remote_control(self, agent: str, proc: subprocess.Popen, master: int) -> None:
        """Types /remote-control hipcmps-<agent> into a Claude terminal once it has drawn. Skipped if that terminal has stopped or been replaced."""
        started = time.time()
        deadline = started + BRIEFING_WAIT_MAX_S
        while time.time() < deadline:
            if proc.poll() is not None or self.procs.get(agent, (None, None))[1] != master:
                self._log_event(agent, "remote control skipped: CLI stopped before it was sent")
                return
            if self.last_output.get(agent) is not None and time.time() - started >= REMOTE_CONTROL_DELAY_S:
                break
            time.sleep(0.5)
        if proc.poll() is not None or self.procs.get(agent, (None, None))[1] != master:
            self._log_event(agent, "remote control skipped: CLI stopped before it was sent")
            return
        # A busy Claude queues typed text without submitting it, so wait until the terminal is Idle (no output for 10 seconds).
        idle_deadline = time.time() + REMOTE_CONTROL_IDLE_MAX_S
        while time.time() < idle_deadline and self.info(agent)["status"] == "Working":
            if proc.poll() is not None or self.procs.get(agent, (None, None))[1] != master:
                self._log_event(agent, "remote control skipped: CLI stopped before it was sent")
                return
            time.sleep(2)
        try:
            self.send_line(agent, f"/remote-control hipcmps-{agent}")
            self._log_event(agent, "remote control sent")
        except (OSError, RuntimeError) as cause:
            self._log_event(agent, f"remote control failed: {cause}")

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
        # os.write can accept only part of a large paste, so keep writing until every byte is in.
        view = memoryview(data.encode("utf-8"))
        while view:
            view = view[os.write(running[1], view):]

    def send_line(self, agent: str, text: str) -> None:
        """Types the text, then presses Enter as its own write. A TUI such as Claude Code reads text and a trailing Enter in one write as a paste, so the Enter is ignored and the text sits in the input bar unsent."""
        self.write(agent, text)
        time.sleep(SUBMIT_DELAY_S)
        self.write(agent, "\r")

    def resize(self, agent: str, rows: int, cols: int) -> None:
        running = self.procs.get(agent)
        if running is not None and running[0].poll() is None:
            self._resize_running(running[0], running[1], rows, cols)

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
        if found is None and folder:
            found = cli_sessions.opencode_last_tool(folder)
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

    @classmethod
    def _resize_running(cls, proc: subprocess.Popen, fd: int, rows: int, cols: int) -> None:
        """Set a running CLI's terminal size and tell it the size changed.

        The CLI runs in its own session with no controlling terminal, so the kernel does not send it
        the window-change signal by itself. Without the signal the CLI keeps drawing for its old width,
        which shows as overlapping and missing letters once the panel is a different width.
        """
        cls._resize(fd, rows, cols)
        try:
            # start_new_session makes the CLI its own group leader, so this reaches it and its children.
            os.killpg(proc.pid, signal.SIGWINCH)
        except (ProcessLookupError, PermissionError):
            pass

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
                with self.lock:
                    stale = self.procs.get(agent, (None, None))[0] is not proc
                if stale:
                    # The CLI this output came from was replaced by a model switch: its output must not reach the new screen.
                    continue
                self.last_output[agent] = time.time()
                screen = self.screens.setdefault(agent, bytearray())
                screen += chunk
                if len(screen) > SCREEN_BYTES:
                    # Cut the oldest output at a line break, so the replay never starts mid-sequence (a half escape code or half UTF-8 character shows as garbage).
                    cut = len(screen) - SCREEN_BYTES
                    newline = screen.find(b"\n", cut, cut + 4096)
                    del screen[: (newline + 1 if newline != -1 else cut)]
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
                    self._log_event(agent, "stopped")
            stopped_by_us = agent in self.stopping
            self.stopping.discard(agent)
            with self.lock:
                superseded = agent in self.replaced and self.procs.get(agent, (None, None))[0] is not proc
                if superseded:
                    self.replaced.discard(agent)
            if superseded:
                return
            if code != 0 and not stopped_by_us:
                # Says what a failed exit usually means, so the terminal shows an error message, not just a code.
                self.emit({"event": "terminal", "agent": agent, "data": f"\r\nError: the CLI stopped with code {code}. Check that it is installed and signed in, then open it again.\r\n"})
            # A stop we asked for is reported as stopped, not as a failed exit code.
            self.emit({"event": "terminal", "agent": agent, "exit": code, "stopped": stopped_by_us})


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


def _ollama_running() -> bool:
    """True when the Ollama server answers on this computer. Waits at most one second."""
    import urllib.request

    try:
        with urllib.request.urlopen("http://127.0.0.1:11434/api/tags", timeout=1):
            return True
    except OSError:
        return False


def engine_problem(provider: str) -> str | None:
    """Why the provider cannot run on this computer, or None when it can. Checked before the Monitor switches engine."""
    from ai.keys import get_key

    if provider in OPENCODE_FOR:
        if shutil.which("opencode") is None:
            return "OpenCode is not installed. Install OpenCode, then apply again."
        env_name = OPENCODE_FOR[provider][1]
        if env_name and not get_key(provider):
            return f"No {provider} key is saved. Add it under Keys, then apply again."
        return None
    name = CLI_FOR.get(provider)
    if name is None:
        return f'The terminal does not run "{provider}" yet.'
    if shutil.which(name) is None:
        return f"{name} is not installed. Install it, then apply again."
    if name == "ollama" and not _ollama_running():
        return "Ollama is not running. Start it, then apply again."
    return None


def provider_env(provider: str) -> dict[str, str]:
    """The API key an OpenCode provider needs, read from the app's key store; empty when none is saved."""
    if provider not in OPENCODE_FOR:
        return {}
    from ai.keys import get_key

    env_name = OPENCODE_FOR[provider][1]
    key = get_key(provider) if env_name else None
    return {env_name: key} if key else {}


# Tools a blocked agent may not use in Claude Code: no shell, no file writes, no web.
BLOCKED_CLAUDE_TOOLS = ("Bash", "Write", "Edit", "NotebookEdit", "WebFetch", "WebSearch", "mcp__vault")


# The briefing pointer is typed in once a CLI has printed and had BRIEFING_DELAY_S to draw its screen. It does not wait for quiet: TUIs such as OpenCode keep redrawing, so quiet never came and the pointer was dropped.
BRIEFING_DELAY_S = 6.0
BRIEFING_WAIT_MAX_S = 60.0
# Gap between typing a message and pressing Enter, so the CLI reads them as typing and not as one paste.
SUBMIT_DELAY_S = 0.5
# A Claude terminal gets /remote-control this long after it first draws.
REMOTE_CONTROL_DELAY_S = 15.0
# How long to wait for an idle Claude terminal before typing /remote-control anyway.
REMOTE_CONTROL_IDLE_MAX_S = 900.0


def _command(agent: str, provider: str, model: str = "", briefing: str = "", vault: str | None = None, block_tools: bool = False, resume: bool = False) -> list[str]:
    # resume: the agent already ran on this engine, so its CLI continues the last session in its folder (each CLI scopes "last" to the working folder).
    if provider in OPENCODE_FOR:
        binary = shutil.which("opencode")
        if binary is None:
            raise RuntimeError("opencode is not installed. Install OpenCode, then open this terminal again.")
        if not model:
            raise RuntimeError(f"Pick a model for {provider} first.")
        # OpenCode takes the briefing pointer as its first prompt: typed input sent to its screen was not taken.
        pointer = ["--prompt", f"Your briefing is in {briefing}. Read it now and follow it for this session."] if briefing else []
        return [binary, *(["--continue"] if resume else []), "-m", f"{OPENCODE_FOR[provider][0]}/{model}", *pointer]
    name = CLI_FOR.get(provider)
    if name is None:
        raise RuntimeError(f'The terminal does not run "{provider}" yet.')
    binary = shutil.which(name)
    if binary is None:
        raise RuntimeError(f"{name} is not installed. Install it, then sign in with `{name}` in a terminal.")
    if name == "ollama":
        # Ollama's run command keeps no session between starts, so there is nothing to resume.
        return [binary, "run", model]
    if name == "agy":
        # Antigravity takes the model as a flag (`agy --model <name>`).
        args = [binary, "--continue"] if resume else [binary]
        return args + (["--model", model] if model else [])
    if name == "codex":
        # Codex takes the model as `--model <name>`; a blocked agent runs in Codex's read-only sandbox.
        args = [binary, "resume", "--last"] if resume else [binary]
        args += ["--model", model] if model else []
        return args + (["--sandbox", "read-only"] if block_tools else [])
    if name == "gemini":
        # Gemini CLI takes the model as `--model <name>`, so a model change reaches it.
        args = [binary, "--resume", "latest"] if resume else [binary]
        return args + (["--model", model] if model else [])
    if name != "claude":
        return [binary]
    entry = cli_sessions.get(agent)
    # Resume whenever Claude Code has saved this session, so its history is kept; otherwise start it under the same id.
    flag = "--resume" if cli_sessions.has_transcript(entry["id"]) else "--session-id"
    # Added agents get no access to the app's own code: Read, Edit and Write under the app folder are denied.
    # Claude Code reads a single leading slash as project-relative, so an absolute path needs a double slash to match.
    # Claude Code rejects a Write rule here ("never matches"); an Edit rule covers writes too.
    rules = [f"{tool}(/{ROOT}/**)" for tool in ("Read", "Edit")]
    if block_tools:
        # "Block tools": the agent may not run a shell, write files or use the web.
        rules += list(BLOCKED_CLAUDE_TOOLS)
    # The briefing applies to every start, resumed or new: it sets the rules (e.g. answer from the vault) for this run.
    brief = ["--append-system-prompt-file", briefing] if briefing else []
    # The vault is open to read and search; agents cannot run rm. Hub notes are protected from deletion in the app's tools.
    vault_dir = ["--add-dir", vault] if vault else []
    # The terminal gets the same vault tools as the chat, so its deletes go through the app's checks, not a shell.
    # A blocked agent gets no vault tools either: "block tools" means no shell and no MCP tools.
    vault_tools = (
        ["--mcp-config", mcp_config(vault), "--allowedTools", *[f"mcp__vault__{name}" for name in VAULT_TOOLS]] if vault and not block_tools else []
    )
    return [
        binary,
        flag,
        entry["id"],
        *(["--model", model] if model else []),
        *vault_dir,
        *vault_tools,
        # The hive is where the agent writes its outbox, so it is a folder the agent may write to.
        "--add-dir",
        str(HIVE_DIR),
        "--disallowedTools",
        *rules,
        # The main agent gets a fenced shell: no delete, move, git, network or privilege commands, and none that names the app folder.
        # Best effort only: a shell can still reach files that no pattern names. Normal agents get no shell.
        *(
            [f"Bash({cmd}:*)" for cmd in ("rm", "rmdir", "mv", "cp", "git", "sudo", "chmod", "chown", "curl", "wget", "dd", "kill", "pkill", "ps", "pgrep", "top", "htop", "lsof", "ss", "netstat", "pidof", "claude")]
            + [f"Bash(* {ROOT}*)"]
            if agent == "hippoherman"
            else ["Bash"]
        ),
        *brief,
    ]
