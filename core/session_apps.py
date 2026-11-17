"""The connected apps as backend calls: the catalogue, connect, disconnect and one app's numbers.

Keys go to the system keychain and are never returned, logged or written to a file.
"""

from pathlib import Path
from typing import Any

from keyring.errors import KeyringError

from ai import keys, network
from core import apps
from core.session_shared import KEYCHAIN_MISSING

KEY_MAX = 4000


def _account(app_id: str) -> str:
    return f"app-{app_id}"


class AppsPart:
    @property
    def apps_path(self) -> Path:
        return self.storage / "apps.json"

    def apps_list(self) -> dict[str, Any]:
        return {
            "apps": apps.catalogue(
                lambda app_id: keys.get_key(_account(app_id)) is not None,
                lambda app_id: keys.key_hint(_account(app_id)),
                apps.load_fields(self.apps_path),
            ),
            "network": network.mode(),
        }

    def app_connect(self, request: dict[str, Any]) -> dict[str, Any]:
        app = apps.app_for(request.get("id"))
        token = request.get("key")
        if not isinstance(token, str) or not token.strip():
            raise ValueError("Paste the key for this app.")
        if len(token) > KEY_MAX or any(ch in token for ch in "\r\n"):
            raise ValueError("That does not look like a key.")
        fields = apps.check_fields(app, request.get("fields"))
        try:
            keys.set_key(_account(app.id), token.strip())
        except KeyringError as error:
            raise ValueError(KEYCHAIN_MISSING) from error
        apps.save_fields(self.apps_path, app.id, fields)
        self.note("setting", text=f"connected the app {app.name}")
        return self.apps_list()

    def app_disconnect(self, request: dict[str, Any]) -> dict[str, Any]:
        app = apps.app_for(request.get("id"))
        try:
            keys.clear_key(_account(app.id))
        except KeyringError as error:
            raise ValueError(KEYCHAIN_MISSING) from error
        apps.save_fields(self.apps_path, app.id, None)
        self.note("setting", text=f"disconnected the app {app.name}")
        return self.apps_list()

    def app_board(self, request: dict[str, Any]) -> dict[str, Any]:
        app = apps.app_for(request.get("id"))
        if network.mode() not in ("converse", "open"):
            raise ValueError(
                f"The network is {network.mode().capitalize()}, so {app.name} cannot be read. "
                "Change it in Settings, Agents."
            )
        token = keys.get_key(_account(app.id))
        if token is None:
            raise ValueError(f"{app.name} is not connected. Connect it in Settings, Dashboards.")
        fields = apps.check_fields(app, apps.load_fields(self.apps_path).get(app.id))
        fetch = self.__dict__.get("_apps_fetch", apps.http_get)  # a test puts a fake here
        return {"id": app.id, "name": app.name, "numbers": apps.read(app, token, fields, fetch)}
