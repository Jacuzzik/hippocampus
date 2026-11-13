"""Turns a request line into a call on the session: one table of handlers, checked against `core/methods.py`."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from core import methods
from core.session_shared import issues_in

Handler = Callable[[dict[str, Any]], dict[str, Any]]


class DispatchPart:
    def handlers(self) -> dict[str, Handler]:
        """Every method, as a function of the request. Methods that take no input ignore it."""

        def plain(call: Callable[[], dict[str, Any]]) -> Handler:
            return lambda _request: call()

        def terminal(name: str) -> Handler:
            return lambda request: self.terminal(name, request)

        return {
            **{
                name: plain(call)
                for name, call in {
                    "graph": self.graph,
                    "account": self.account,
                    "tasks": self.tasks,
                    "inbox": self.inbox,
                    "settings": self.settings_view,
                    "memory": self.memory_notes,
                    "sign_out": self.sign_out,
                    "remove_data": self.remove_data,
                    "workspaces": self.workspaces,
                    "tools": self.tools,
                    "cards": self.card_list,
                    "engine": self.engine,
                    "network": self.network_state,
                    "budget": self.budget,
                    "budget_allow": self.budget_allow,
                    "asks": self.asks_waiting,
                    "memory_status": self.memory_status,
                    "jobs": self.jobs,
                    "helpers": self.helpers_state,
                    "watchers": self.watchers_state,
                    "system": self.system_state,
                    "skills": self.skills_state,
                    "keys": self.keys,
                    "webhooks": self.webhooks_state,
                    "agents": self.agents_state,
                    "provider_status": self.provider_status,
                    "local_status": self.local_status,
                    "doctor": self.doctor,
                    "settings_export": self.settings_export,
                    "link_doctor": self.link_doctor,
                    "crashes": self.crashes,
                    "clear_crashes": self.clear_crashes,
                }.items()
            },
            "open": lambda request: self.open(Path(request["vault"])),
            "read": self.read,
            "note_text": self.note_text,
            "note_save": self.note_save,
            "note_delete": self.note_delete,
            "note_colour": self.note_colour,
            "sign_in": self.sign_in,
            "chat": self.chat,
            "create_workspace": self.create_workspace,
            "agent_session": self.agent_session,
            "terminal_context": self.terminal_context,
            "terminal_traces": self.terminal_traces,
            "terminal_command": self.terminal_command,
            "terminal_start": terminal("terminal_start"),
            "terminal_input": terminal("terminal_input"),
            "terminal_resize": terminal("terminal_resize"),
            "terminal_stop": terminal("terminal_stop"),
            "git_status": self.git_status,
            "open_folder": self.open_folder,
            "chat_history": self.chat_history_load,
            "chat_history_save": self.chat_history_store,
            "current_session": self.current_session,
            "new_session": self.new_session,
            "confirm": self.confirm,
            "answer": self.answer,
            "set_tools": self.set_tools,
            "card_create": self.card_create,
            "card_update": self.card_update,
            "issues": lambda request: issues_in(request.get("folder")),
            "tokens": self.tokens,
            "set_engine": self.set_engine,
            "stop": plain(self.stop),
            "set_network": self.set_network,
            "set_vault": self.set_vault,
            "set_budget": self.set_budget,
            "activity": self.activity,
            "memory_search": self.memory_search,
            "set_job": self.set_job,
            "start_helper": self.start_helper,
            "remove_skill": self.remove_skill,
            "install_skill": self.install_skill,
            "open_skill_folder": self.open_skill_folder,
            "share": self.share_note,
            "save_agents": self.save_agents,
            "save_key": self.save_key,
            "clear_key": self.clear_key,
            "save_webhook": self.save_webhook,
            "delete_webhook": self.delete_webhook,
            "run_webhook": self.run_webhook,
            "record_crash": self.record_crash,
            "set_agent_shell": self.set_agent_shell,
            "task_send": self.task_send,
            "settings_import": self.settings_import,
            "inbox_search": self.inbox_search,
            "inbox_thread": self.inbox_thread,
            "logs": self.logs,
            "connectors": self.connectors,
        }

    def stop(self) -> dict[str, Any]:
        self.kill.trigger()
        return {"stopped": True}

    def dispatch(self, request: dict[str, Any]) -> dict[str, Any]:
        name = methods.check(request)
        return self.handlers()[name](request)
