"""Turns a request line into a call on the session: one table of handlers, checked against `core/methods.py`."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

from core import methods, phone
from core.github_board import board as github_board
from core.session_shared import ci_in, issues_in

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
                    "missions": self.missions,
                    "helpers": self.helpers_state,
                    "watchers": self.watchers_state,
                    "fleet": self.fleet_state,
                    "playbooks": self.playbook_list,
                    "breakers": self.breakers_state,
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
            "note_history": self.note_history,
            "note_version": self.note_version,
            "note_restore": self.note_restore,
            "handoff": self.handoff,
            "playbook_run": self.playbook_run,
            "search_all": self.search_all,
            "mcp_servers": self.mcp_servers,
            "mcp_add": self.mcp_add,
            "mcp_remove": self.mcp_remove,
            "chat": self.chat,
            "create_workspace": self.create_workspace,
            "agent_session": self.agent_session,
            "terminal_context": self.terminal_context,
            "remote_status": self.remote_status,
            "terminal_traces": self.terminal_traces,
            "terminal_rebrief": self.terminal_rebrief,
            "briefing_preview": self.briefing_preview,
            "agent_pins": self.agent_pins,
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
            "card_from_note": self.card_from_note,
            "card_note": self.card_note,
            "card_update": self.card_update,
            "issues": lambda request: issues_in(request.get("folder")),
            "ci": lambda request: ci_in(request.get("folder")),
            "github_board": lambda request: github_board(request.get("repo")),
            "phone_status": lambda request: phone.status(),
            "phone_mirror": lambda request: phone.mirror(
                request.get("serial"), request.get("approve")
            ),
            "phone_view": lambda request: phone.view(request.get("serial"), request.get("approve")),
            "phone_stop": lambda request: phone.stop(request.get("serial")),
            "phone_control": lambda request: phone.control(
                request.get("serial"), request.get("action"), request.get("approve")
            ),
            "user_account": lambda request: self.user_account.status(),
            "user_sign_in": lambda request: self.user_account.start(open_browser=True),
            "user_sign_in_cancel": lambda request: self.user_account.cancel(),
            "user_sign_out": lambda request: self.user_account.sign_out(),
            "user_delete": lambda request: self.user_account.delete(),
            "user_consent": lambda request: self.user_account.set_consent(
                request.get("sync") is True, request.get("usage") is True
            ),
            "user_sync_save": self.user_sync_save,
            "user_sync_fetch": self.user_sync_fetch,
            "user_shares": self.user_shares,
            "user_share_delete": self.user_share_delete,
            "tokens": self.tokens,
            "set_engine": self.set_engine,
            "stop": plain(self.stop),
            "set_network": self.set_network,
            "set_vault": self.set_vault,
            "set_budget": self.set_budget,
            "activity": self.activity,
            "clear_activity": plain(self.clear_activity),
            "save_export": self.save_export,
            "export_notes": plain(self.export_notes),
            "memory_search": self.memory_search,
            "set_job": self.set_job,
            "mission_save": self.mission_save,
            "mission_remove": self.mission_remove,
            "run_job": self.run_job,
            "calendar": self.calendar,
            "calendar_add": self.calendar_add,
            "calendar_remove": self.calendar_remove,
            "calendar_mark": self.calendar_mark,
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
            "set_number": self.set_number,
            "task_send": self.task_send,
            "settings_import": self.settings_import,
            "inbox_search": self.inbox_search,
            "inbox_thread": self.inbox_thread,
            "logs": self.logs,
            "connectors": self.connectors,
            "apps": lambda request: self.apps_list(),
            "provider_usage": lambda request: self.provider_usage(),
            "finance": lambda request: self.finance(),
            "finance_save": self.finance_save,
            "open_link": self.open_link,
            "vault_board": lambda request: self.vault_board(),
            "vault_insights_request": lambda request: self.vault_insights_request(),
            "github_all": lambda request: self.github_all(),
            "app_connect": self.app_connect,
            "app_disconnect": self.app_disconnect,
            "app_board": self.app_board,
        }

    def stop(self) -> dict[str, Any]:
        self.kill.trigger()
        return {"stopped": True}

    def dispatch(self, request: dict[str, Any]) -> dict[str, Any]:
        name = methods.check(request)
        return self.handlers()[name](request)
