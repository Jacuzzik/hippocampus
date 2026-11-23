"""Money from receipts as backend calls: connect a Gmail address with an app password and scan it,
add files the user downloaded (Google Takeout's Play Store part, Apple's data copy, a bank
statement), and show the subscriptions, purchases, sales and refunds found in all of them together.

The password goes to the system keychain and is never returned, logged or written to a file. The
address and what the last scan read are kept in storage/mail.json, the added files' events in
storage/purchase-files.json (the files themselves are not kept)."""

import base64
import binascii
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from keyring.errors import KeyringError

from ai import keys, network
from core import mail_receipts, purchase_files, safe_write
from core.session_shared import KEYCHAIN_MISSING

ACCOUNT = "mail-gmail"
ADDRESS = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,190}\.[a-z]{2,}$", re.I)
FILES_KEPT = 20


def _read_json(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


class MailPart:
    @property
    def mail_path(self) -> Path:
        return self.storage / "mail.json"

    @property
    def purchase_files_path(self) -> Path:
        return self.storage / "purchase-files.json"

    def _mail_saved(self) -> dict[str, Any]:
        return _read_json(self.mail_path)

    def _files_saved(self) -> list[dict[str, Any]]:
        files = _read_json(self.purchase_files_path).get("files")
        return [f for f in files if isinstance(f, dict)] if isinstance(files, list) else []

    def mail_status(self) -> dict[str, Any]:
        saved = self._mail_saved()
        address = saved.get("account", "")
        connected = bool(address) and keys.get_key(ACCOUNT) is not None
        scan = saved if connected else {}
        files = self._files_saved()
        events = [e for e in scan.get("events") or [] if isinstance(e, dict)]
        events += [e for f in files for e in f.get("events") or [] if isinstance(e, dict)]
        today = datetime.now().astimezone().date()
        sources = [
            {
                "kind": "file",
                "name": f.get("name", ""),
                "added": f.get("added", ""),
                "events": len(f.get("events") or []),
            }
            for f in files
        ]
        return {
            "connected": connected,
            "account": address if connected else "",
            "scanned_at": scan.get("scanned_at", ""),
            "read": scan.get("read", 0),
            "messages": len(scan.get("events") or []),
            "files": sources,
            "found": mail_receipts.summarise(events, today) if events else None,
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
        keep = {k: found[k] for k in ("account", "scanned_at", "read", "events")}
        safe_write.write_text(self.mail_path, json.dumps(keep, indent=2))
        return self.mail_status()

    def purchases_import(self, request: dict[str, Any]) -> dict[str, Any]:
        name = str(request.get("name") or "").strip()[:120] or "file"
        try:
            data = base64.b64decode(str(request.get("data") or ""), validate=True)
        except (binascii.Error, ValueError) as error:
            raise ValueError("The file could not be read.") from error
        events = purchase_files.read(name, data)
        files = [f for f in self._files_saved() if f.get("name") != name]
        files.append(
            {
                "name": name,
                "added": datetime.now().astimezone().isoformat(timespec="seconds"),
                "events": events,
            }
        )
        safe_write.write_text(
            self.purchase_files_path, json.dumps({"files": files[-FILES_KEPT:]}, indent=2)
        )
        self.note("setting", text=f"read purchases from the file {name}")
        return self.mail_status()

    def purchases_remove(self, request: dict[str, Any]) -> dict[str, Any]:
        name = str(request.get("name") or "")
        files = self._files_saved()
        if not any(f.get("name") == name for f in files):
            raise ValueError("No added file has that name.")
        rest = [f for f in files if f.get("name") != name]
        safe_write.write_text(self.purchase_files_path, json.dumps({"files": rest}, indent=2))
        return self.mail_status()
