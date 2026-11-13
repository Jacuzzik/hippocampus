# Security review: accounts and the website

Written before any account code exists, so the design is checked first. Nothing here is built yet.
The app works fully without an account and must keep doing so (plan item 14.08).

## What is in place today

| Area | State | Check |
|---|---|---|
| Agent shell | Off by default; on, it runs inside bubblewrap | `tests/core/test_sandbox.py`, `test_agent_shell.py` |
| Messages between agents | Sender is taken from the folder, not the message | `tests/core/test_inbox.py` |
| API keys | System keychain only; masked in logs | `tests/core/test_app_log.py` |
| Settings and data files | Written to a temporary file, then renamed | `tests/core/test_settings_transfer.py` |
| Outside calls | Every program and web call has a time limit | `tests/core/test_time_limits.py` |
| Dependencies | Scanned in CI (Python, Node, Rust), report only | `.github/workflows/ci.yml`, job `audit` |
| Website | Static pages, no scripts, no cookies, not deployed | `website/` |

## What an account would add, and what could go wrong

| Risk | Who gains | Rule that prevents it |
|---|---|---|
| A stolen sign-in token is used from another computer | Thief reads synced settings | Token lives in the system keychain only; short life; sign-out deletes it and tells the server |
| The sign-in page is copied (phishing) | Thief gets the account | No passwords at all: email link or GitHub/Google sign-in through a hosted provider |
| The sign-in link is opened by the wrong app | Thief completes sign-in | Use the provider's device or PKCE flow with a one-time code checked by the app |
| Sync uploads something private | Notes or keys leave the computer | Sync is opt-in and covers settings, agent definitions and briefings only. Notes, keys and the vault path are never synced; a test must prove the upload contains none |
| Many sign-in tries against one address | Lockout or account takeover | Rate limits at the provider; no account existence hints in error text |
| The app stops working when the server is down | Everyone loses access | Every account call has a time limit and a fallback; the app starts and runs offline |
| Usage data is sent without a yes | Loss of trust | Telemetry off by default; one consent screen in plain words; the yes is stored and can be taken back |

## Decisions the owner must make before any of this is built

1. Which hosted sign-in provider (the plan suggests one with GitHub, Google and email link).
2. The domain for the website and the sign-in pages.
3. Whether sync is wanted at all in the first release.

## Before launch (none done yet)

- [ ] Threat model above reviewed by a second person.
- [ ] Tests: sign-in happy path, expired token, offline start, sign-out wipes the token, sync upload contains no note text and no key.
- [ ] Rate limits confirmed at the provider.
- [ ] Privacy page and SECURITY.md name the provider and what it stores.
- [ ] A staging environment exists and the tests run against it.
