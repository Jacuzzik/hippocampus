"""Money from email receipts as backend calls: connect a Gmail address with an app password, scan it,
show what was found, and disconnect. The password goes to the system keychain and is never returned,
logged or written to a file; the address and the last scan are kept in storage/mail.json."""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from keyring.errors import KeyringError

from ai import keys, network
from core import mail_receipts, safe_write
from core.session_shared import KEYCHAIN_MISSING

ACCOUNT = "mail-gmail"
ADDRESS = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[a-z]{2,}$", re.I)


class MailPart:
    @property
    def mail_path(self) -> Path:
        return self.storage / "mail.json"

    def _mail_saved(self) -> dict[str, Any]:
        try:
            data = json.loads(self.mail_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    def mail_status(self) -> dict[str, Any]:
        saved = self._mail_saved()
        address = saved.get("account", "")
        connected = bool(address) and keys.get_key(ACCOUNT) is not None
        return {
            "connected": connected,
            "account": address if connected else "",
            "found": saved.get("found") if connected else None,
            "network": network.mode(),
        }

    def mail_connect(self, request: dict[str, Any]) -> dict[str, Any]:
        address = str(request.get("email") or "").strip()
        password = re.sub(r"\s+", "", str(request.get("password") or ""))
        if not ADDRESS.match(address):
            raise ValueError("Type the Gmail address the receipts go to.")
        if not 8 <= len(password) <= 64:
            raise ValueError("Paste the 16-letter app password from your Google account.")
        try:
            keys.set_key(ACCOUNT, password)
        except KeyringError as error:
            raise ValueError(KEYCHAIN_MISSING) from error
        safe_write.write_text(self.mail_path, json.dumps({"account": address}, indent=2))
        self.note("setting", text=f"connected the email {address} to read receipts")
        return self.mail_scan()

    def mail_disconnect(self) -> dict[str, Any]:
        try:
            keys.clear_key(ACCOUNT)
        except KeyringError as error:
            raise ValueError(KEYCHAIN_MISSING) from error
        self.mail_path.unlink(missing_ok=True)
        self.note("setting", text="disconnected the email for receipts")
        return self.mail_status()

    def mail_scan(self) -> dict[str, Any]:
        address = self._mail_saved().get("account", "")
        password = keys.get_key(ACCOUNT)
        if not address or password is None:
            raise ValueError("No email is connected. Connect Gmail first.")
        if network.mode() not in ("converse", "open"):
            raise ValueError(
                f"The network is {network.mode().capitalize()}, so the email cannot be read. "
                "Change it in Settings, Agents."
            )
        get = self.__dict__.get("_mail_fetch", mail_receipts.fetch)  # a test puts a fake here
        found = mail_receipts.scan(address, password, datetime.now().astimezone().date(), get)
        safe_write.write_text(
            self.mail_path, json.dumps({"account": address, "found": found}, indent=2)
        )
        return self.mail_status()
