"""What the Settings pages read: the settings view, export and import, the doctor, provider and local status, and the shell."""

import shutil
import tomllib
import urllib.request
from dataclasses import asdict, replace
from pathlib import Path
from typing import Any

from core import (
    __version__,
    app_log,
    crash_log,
    doctor,
    safe_write,
    sandbox,
)
from core.settings import (
    ROOT,
    load_settings,
    save_agent_shell,
)
from core.terminal import sandbox_for


class SettingsPart:
    def settings_view(self) -> dict[str, Any]:
        # Read-only view of the saved settings. API keys are never included.
        s = self.settings
        return {
            "general": {"vault": str(s.vault) if s.vault else None, "network": s.network_mode},
            "agents": {
                "provider": s.provider,
                "model": s.provider_model or s.claude_model,
                "ollama": s.ollama_model,
            },
            "budgets": {
                "app": asdict(s.budget),
                "assistant": asdict(s.assistant_budget),
                "max_tool_calls": s.max_tool_calls,
            },
            "memory": {"max_bytes": s.memory_max_bytes},
            "shell": self.shell_state(),
        }

    def settings_export(self) -> dict[str, Any]:
        """The settings file as text, to carry to another computer. Keys are never in it: they live in the keychain."""
        path = self.settings_path
        return {
            "text": path.read_text(encoding="utf-8") if path.is_file() else "",
            "path": str(path),
        }

    def settings_import(self, request: dict[str, Any]) -> dict[str, Any]:
        """Replace the settings file with the given text. A text that does not load is refused and nothing changes."""
        text = request.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError('"settings_import" needs the settings "text"')
        check = self.settings_path.with_name(self.settings_path.name + ".check")
        try:
            check.write_text(text, encoding="utf-8")
            loaded = load_settings(check)  # raises with the reason when a value is wrong
        except tomllib.TOMLDecodeError as error:
            raise ValueError(f"This is not a settings file: {error}") from error
        finally:
            check.unlink(missing_ok=True)
        safe_write.write_text(self.settings_path, text)
        self.settings = loaded
        self.note("setting", text="settings imported")
        return {
            "imported": True,
            "restart": "Restart the app so every part reads the new settings.",
        }

    def doctor(self) -> dict[str, Any]:
        """Everything the app needs, checked in one go, with the next step for each gap."""
        vault = self.settings.vault
        notes = self.indexer.store.counts().get("notes") if self.indexer is not None else None
        rows = [
            doctor.row("Backend", "ok", f"Running, version {__version__}."),
            doctor.check_vault(Path(vault) if vault else None, notes),
            doctor.check_disk(self.storage),
            *doctor.check_clis(self.provider_status()["clis"]),
            doctor.check_sandbox(sandbox.available(), self.settings.agent_shell),
            doctor.check_log(app_log.path(self.storage)),
        ]
        errors = len(crash_log.recent(self.storage, 50))
        rows.append(
            doctor.row("Recorded errors", "ok", "None.")
            if errors == 0
            else doctor.row(
                "Recorded errors",
                "warn",
                f"{errors} in the error log.",
                "Settings > Privacy and data lists them; clear the list once you have read it.",
            )
        )
        return {"checks": rows, "summary": doctor.summary(rows)}

    def local_status(self) -> dict[str, Any]:
        # Is each local model server answering on this computer? Only a quick look at the loopback address.
        servers = [
            ("ollama", "http://127.0.0.1:11434/api/tags"),
            ("lmstudio", "http://127.0.0.1:1234/v1/models"),
            ("vllm", "http://127.0.0.1:8000/v1/models"),
        ]
        rows = []
        for provider, url in servers:
            try:
                with urllib.request.urlopen(url, timeout=1):
                    running = True
            except OSError:
                running = False
            rows.append({"provider": provider, "running": running})
        return {"servers": rows}

    def provider_status(self) -> dict[str, Any]:
        # Is each CLI installed, and is its login file there? Only file names are checked, never contents.
        # logged_in is None where the login file is not known for this CLI.
        home = Path.home()
        clis = [
            (
                "claude",
                "claude",
                "Claude Code",
                home / ".claude" / ".credentials.json",
                "Run `claude` in a terminal and log in.",
            ),
            (
                "codex",
                "codex",
                "Codex",
                home / ".codex" / "auth.json",
                "Run `codex login` in a terminal and finish the browser step.",
            ),
            (
                "gemini-cli",
                "gemini",
                "Gemini CLI",
                None,
                "Run `gemini` in a terminal and pick a login method.",
            ),
            ("antigravity", "agy", "Antigravity", None, "Run `agy` in a terminal and sign in."),
        ]
        rows = []
        for provider, binary, label, login_file, login_steps in clis:
            installed = shutil.which(binary) is not None
            logged_in = None if login_file is None else login_file.exists()
            if not installed:
                steps = f"Install {label} first. {login_steps}"
            elif logged_in is False:
                steps = login_steps
            else:
                steps = ""
            rows.append(
                {
                    "provider": provider,
                    "label": label,
                    "installed": installed,
                    "logged_in": logged_in,
                    "steps": steps,
                }
            )
        return {"clis": rows}

    def shell_state(self) -> dict[str, Any]:
        """Whether every agent has a shell, whether the sandbox can run here, and the rules in plain words."""
        on = self.settings.agent_shell
        usable = sandbox.available()
        return {
            "on": on,
            "sandbox_available": usable,
            "main": sandbox.policy_lines(
                shell=True, sandboxed=on and usable, blocked=False, app_root=ROOT
            ),
            "agents": sandbox.policy_lines(
                shell=on and usable, sandboxed=on and usable, blocked=False, app_root=ROOT
            ),
            "note": (
                "Applies to agents on Claude Code. Other programs (Codex, Gemini, OpenCode) keep their own rules until each is tested in the sandbox."
                if sandbox_for("claude")
                else "The sandbox (bubblewrap) cannot start on this computer, so normal agents get no shell."
            ),
        }

    def set_agent_shell(self, request: dict[str, Any]) -> dict[str, Any]:
        on = request.get("on")
        if not isinstance(on, bool):
            raise ValueError('"set_agent_shell" needs "on": true or false')
        save_agent_shell(on, self.settings_path)
        self.settings = replace(self.settings, agent_shell=on)
        self.note("setting", text=f"shell for all agents turned {'on' if on else 'off'}")
        return self.shell_state()
