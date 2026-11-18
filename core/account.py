"""The user's Hippocampus account (plan section 14): Google sign-in through a hosted sign-in service (Supabase).

Local-first: nothing here is needed to use the app, and it does nothing until the service is set up
(AUTH_URL and AUTH_KEY, or the HIPPOCAMPUS_AUTH_URL / HIPPOCAMPUS_AUTH_KEY variables).

Sign-in, step by step:
  1. `start()` makes a one-time secret (PKCE verifier), opens a tiny web server on 127.0.0.1 and returns the
     service's Google sign-in address, which the window opens in the system browser.
  2. After Google, the service sends the browser back to that local server with a one-time code.
  3. The code and the secret are swapped for tokens. A stolen code is useless without the secret.
  4. The tokens go into the OS keychain, never into a file. Sign-out deletes them.

The app never sees a password, and the user's provider API keys are not involved at all.
"""

import base64
import hashlib
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import webbrowser
from collections.abc import Callable
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any

import keyring
from keyring.errors import KeyringError

from ai import network

# The owner's Supabase project (2026-11-17). The key is the public "publishable" key, safe to ship.
AUTH_URL = "https://qrdehlqmqydphizlznhr.supabase.co"
AUTH_KEY = "sb_publishable_PCRx2rK7SQwNBAJRl_fY9w_05ttd0f3"
KEYCHAIN = "hippocampus-account"
KEYCHAIN_USER = "session"
CONSENT_FILE = "account.json"
WAIT_S = 300  # how long the local server waits for the browser to come back
REFRESH_EARLY_S = 60

DONE_PAGE = (
    "<!doctype html><meta charset=utf-8><title>Hippocampus</title>"
    "<body style='font-family:monospace;padding:40px'><h1>{title}</h1><p>{text}</p></body>"
)

Fetch = Callable[[urllib.request.Request], dict[str, Any]]


class Offline(Exception):
    """The service could not be reached."""


class Refused(Exception):
    """The service answered no (expired or revoked session, bad code)."""


def _fetch(request: urllib.request.Request) -> dict[str, Any]:
    try:
        with urllib.request.urlopen(request, timeout=15) as reply:  # noqa: S310 (https service address)
            body = reply.read()
    except urllib.error.HTTPError as error:
        raise Refused(f"{error.code}") from error
    except (urllib.error.URLError, OSError) as error:
        raise Offline(str(error)) from error
    return json.loads(body) if body else {}


def pkce() -> tuple[str, str]:
    """A secret and its SHA-256 challenge, both URL-safe base64 without padding (RFC 7636)."""
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    return verifier, base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


class Account:
    def __init__(
        self,
        storage: Path,
        fetch: Fetch = _fetch,
        url: str | None = None,
        key: str | None = None,
    ) -> None:
        self.storage = storage
        self.fetch = fetch
        self.url = (
            url if url is not None else os.environ.get("HIPPOCAMPUS_AUTH_URL", AUTH_URL)
        ).rstrip("/")
        self.key = key if key is not None else os.environ.get("HIPPOCAMPUS_AUTH_KEY", AUTH_KEY)
        self.pending: dict[str, Any] | None = None
        self.problem = ""
        self.lock = threading.Lock()

    # The keychain ------------------------------------------------------------------------------
    def _load(self) -> dict[str, Any] | None:
        try:
            raw = keyring.get_password(KEYCHAIN, KEYCHAIN_USER)
        except KeyringError:
            return None
        try:
            return json.loads(raw) if raw else None
        except ValueError:
            return None

    def _save(self, session: dict[str, Any]) -> None:
        keep = ("access_token", "refresh_token", "expires_at", "user")
        keyring.set_password(KEYCHAIN, KEYCHAIN_USER, json.dumps({k: session.get(k) for k in keep}))

    def _wipe(self) -> None:
        try:
            keyring.delete_password(KEYCHAIN, KEYCHAIN_USER)
        except KeyringError:
            pass

    # Talking to the service --------------------------------------------------------------------
    def _call(
        self, path: str, body: dict[str, Any] | None = None, token: str = ""
    ) -> dict[str, Any]:
        if not network.allows_model_calls():
            raise Offline("the network switch is off")
        headers = {"apikey": self.key, "Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        data = json.dumps(body).encode() if body is not None else None
        return self.fetch(
            urllib.request.Request(self.url + path, data=data, headers=headers, method="POST")
        )

    def _stamp(self, session: dict[str, Any]) -> dict[str, Any]:
        if not session.get("expires_at"):
            session["expires_at"] = int(time.time()) + int(session.get("expires_in", 3600))
        return session

    def configured(self) -> bool:
        return bool(self.url and self.key)

    # What the window shows --------------------------------------------------------------------
    def status(self) -> dict[str, Any]:
        base = {
            "configured": self.configured(),
            "waiting": self.pending is not None,
            "consent": self.consent(),
        }
        if self.problem:
            base["problem"] = self.problem
        session = self._load()
        if not session:
            return {**base, "signed_in": False}
        offline = False
        if session.get("expires_at", 0) - REFRESH_EARLY_S < time.time():
            try:
                session = self._refresh(session)
            except Offline:
                offline = True  # keep the old session; the app works the same without the service
            except Refused:
                self._wipe()
                return {
                    **base,
                    "signed_in": False,
                    "problem": "Your sign-in expired. Sign in again.",
                }
        user = session.get("user") or {}
        meta = user.get("user_metadata") or {}
        return {
            **base,
            "signed_in": True,
            "offline": offline,
            "email": user.get("email", ""),
            "name": meta.get("full_name") or meta.get("name") or "",
            "plan": (user.get("app_metadata") or {}).get("plan", "free"),
        }

    def _refresh(self, session: dict[str, Any]) -> dict[str, Any]:
        fresh = self._stamp(
            self._call(
                "/auth/v1/token?grant_type=refresh_token",
                {"refresh_token": session["refresh_token"]},
            )
        )
        fresh.setdefault("user", session.get("user"))
        self._save(fresh)
        return fresh

    # Signing in --------------------------------------------------------------------------------
    def start(self, open_browser: bool = False) -> dict[str, Any]:
        """Open the local return address and give back the sign-in page for the browser."""
        if not self.configured():
            raise ValueError(
                "Accounts are not set up in this build yet. The app works fully without one."
            )
        if not network.allows_model_calls():
            raise ValueError(
                "The network switch is Off. Set it to Converse in Settings > Network to sign in."
            )
        self.cancel()
        verifier, challenge = pkce()
        server = HTTPServer(("127.0.0.1", 0), _handler(self))
        back = f"http://127.0.0.1:{server.server_address[1]}/callback"
        query = urllib.parse.urlencode(
            {
                "provider": "google",
                "redirect_to": back,
                "code_challenge": challenge,
                "code_challenge_method": "s256",
            }
        )
        self.pending = {"verifier": verifier, "server": server, "until": time.monotonic() + WAIT_S}
        self.problem = ""
        threading.Thread(target=self._serve, args=(server,), daemon=True).start()
        url = f"{self.url}/auth/v1/authorize?{query}"
        if open_browser:
            webbrowser.open(url)
        return {"url": url}

    def _serve(self, server: HTTPServer) -> None:
        server.timeout = 1
        while self.pending is not None and self.pending.get("server") is server:
            if time.monotonic() > self.pending["until"]:
                self.problem = "Sign-in timed out. Try again."
                self.cancel()
                break
            server.handle_request()
        server.server_close()

    def finish(self, code: str) -> None:
        """Swap the one-time code for tokens. Called by the local server when the browser comes back."""
        with self.lock:
            if self.pending is None or self.pending.get("used"):
                raise Refused("no sign-in in progress")
            self.pending["used"] = True  # a second callback with another code is refused
            verifier = self.pending["verifier"]
        # Stay "waiting" until the tokens are in the keychain, so the window never sees a gap where the
        # sign-in looks finished but nobody is signed in (it stops polling once waiting is false).
        try:
            session = self._call(
                "/auth/v1/token?grant_type=pkce", {"auth_code": code, "code_verifier": verifier}
            )
            self._save(self._stamp(session))
        except (Offline, Refused) as error:
            self.problem = "Sign-in did not finish. Try again."
            raise Refused(str(error)) from error
        except KeyringError as error:
            self.problem = "No keychain on this computer, so the sign-in could not be kept."
            raise Refused("keychain") from error
        finally:
            self.pending = None

    def cancel(self) -> dict[str, Any]:
        self.pending = None
        return self.status()

    def sign_out(self) -> dict[str, Any]:
        session = self._load()
        if session and session.get("access_token"):
            try:
                self._call("/auth/v1/logout", {}, token=session["access_token"])
            except (Offline, Refused):
                pass  # the local copy goes either way
        self._wipe()
        self.problem = ""
        return self.status()

    def delete(self) -> dict[str, Any]:
        """Ask the service to delete the account and everything it holds, then sign out here."""
        session = self._load()
        if not session:
            raise ValueError("Sign in first.")
        try:
            self._call("/functions/v1/delete-account", {}, token=session["access_token"])
        except Offline as error:
            raise ValueError("Could not reach the account service. Nothing was deleted.") from error
        except Refused as error:
            raise ValueError("The account service refused. Nothing was deleted.") from error
        self._wipe()
        return self.status()

    # Consent (14.12): both off until the user turns them on --------------------------------------
    def consent(self) -> dict[str, bool]:
        try:
            saved = json.loads((self.storage / CONSENT_FILE).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            saved = {}
        return {k: saved.get(k) is True for k in ("sync", "usage")} | {
            "asked": saved.get("asked") is True
        }

    def set_consent(self, sync: bool, usage: bool) -> dict[str, Any]:
        path = self.storage / CONSENT_FILE
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"sync": sync, "usage": usage, "asked": True}), encoding="utf-8")
        return self.status()


def _handler(account: Account) -> type[BaseHTTPRequestHandler]:
    class Back(BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            pass

        def do_GET(self) -> None:
            path, _, query = self.path.partition("?")
            code = urllib.parse.parse_qs(query).get("code", [""])[0]
            if path != "/callback" or not code:
                self.send_error(404)
                return
            try:
                account.finish(code)
                page = DONE_PAGE.format(
                    title="Signed in", text="You can close this tab and go back to Hippocampus."
                )
            except Refused:
                page = DONE_PAGE.format(
                    title="Sign-in did not finish", text="Go back to Hippocampus and try again."
                )
            body = page.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    return Back
