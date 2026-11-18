# Accounts plan

Status: **agreed 2026-11-17** with the recommendations below (Supabase, update notices and plan first, no paid
plan in the beta, no domain yet). The app side is built (`core/account.py`, Settings > General > Account,
`supabase/functions/delete-account`), tested against a stand-in service. It switches on when the two values in
"Owner setup" are filled in.

## Owner setup (only the owner can do these; all free)

1. **Supabase project:** supabase.com > New project (Free plan). Note the project address
   (`https://<ref>.supabase.co`).
2. **Google sign-in client:** console.cloud.google.com > APIs & Services > OAuth consent screen (External,
   name "Hippocampus") > Credentials > Create OAuth client ID > Web application. Authorised redirect URI:
   `https://<ref>.supabase.co/auth/v1/callback`.
3. **Connect them:** Supabase > Authentication > Sign In / Providers > Google: switch on, paste the client ID
   and secret.
4. **Let the app's return address in:** Supabase > Authentication > URL Configuration > Redirect URLs: add
   `http://127.0.0.1:*/callback`.
5. **Give Claude two public values:** the project address and the **anon public** key (Supabase > Project
   Settings > API). Never the `service_role` key. Claude puts them in `core/account.py` (AUTH_URL, AUTH_KEY),
   deploys `delete-account` (needs `supabase login` by the owner once), and runs the tests against the real
   project (14.14).
Covers plan items 14.01–14.14 and M.22. The rules already agreed: the app works fully with no account (14.08),
sign-in is with a Google account (owner, 2026-11-13), and the security checks in `docs/SECURITY-REVIEW.md`
pass before launch (14.13).

## How Munder Difflin does it (read from its installed app, v0.5.7)

- **Sign-in opens the browser** at its website (`/desktop/signin`). After sign-in the website hands the app a
  token through a link back into the app. The app never shows a password box.
- **Plan and licence** are bought on the website (`/checkout`); a team can share a plan with a **team code**.
- **Updates** come from the website's release list (`app./releases`).
- **Work stays local.** Agents, notes and settings live on the computer; signing out keeps them.

That model fits Hippocampus: the website is already built (`website/`), and local-first is already a rule.

## Proposed design

| Part | Proposal | Plan item |
| --- | --- | --- |
| Why have an account | Day one: update notices and the plan (free or supporter). Later, only if wanted: sync of settings and briefings, share links, team spaces. | 14.02–14.07 |
| Sign-in method | Google only, in the system browser, through a hosted sign-in service (it holds the user list, so we keep no passwords). The browser returns to the app with a one-time code (PKCE, so a stolen code is useless). | 14.09 |
| Where the token lives | The OS keychain (Tauri keychain plugin). Sign-out deletes it. Provider API keys never leave the computer. | 14.10 |
| Screens | Settings > Account: signed out shows one "Sign in with Google" button; signed in shows name, plan, this computer's devices, Sign out, Delete account. Hidden until the service is live. | 14.11, M.22, 14.01 |
| Consent | One screen before anything leaves the computer: sync off, usage reports off; plain words and a link to the privacy page. | 14.12 |
| Website side | Sign-in page, account page (download, plan, devices, delete), all on the existing static site plus the sign-in service. | 14.03, 15.03, 15.04 |
| Tests | Sign in, expired token, offline, switching accounts, deleting an account, against a staging copy of the service. | 14.14 |

## What it costs

Free to start: the hosted sign-in services all have a free tier far above a beta's size; the website is static
on Vercel. Payments (if supporter plans come) add a payment provider and its fees.

## Decisions for the owner

1. **Sign-in service:** Supabase Auth (free, also gives a database for sync later), Clerk (nicest screens,
   free to 10,000 users) or Firebase Auth (Google's own). Recommendation: **Supabase**.
2. **Domain** for the website and the sign-in return address (for example `hippocampus.app`, whatever is free).
3. **Day-one scope:** only update notices and plan (recommended), or sync from the start.
4. **Paid plan:** none for the beta (recommended), or a supporter plan at launch.
5. **Accounts you create** (only you can): the Google Cloud OAuth client, the sign-in service project, the domain.

After these five answers the build order is: sign-in service and keychain (no screens) → Settings > Account →
website account page → tests on staging → security review → switch on.

## Phase 2: what an account unlocks (14.02–14.07), decided 2026-11-18

The owner asked Claude to plan these and decide. Rules kept: local-first, everything off until the user turns it
on, free for everyone in the beta, nothing runs in the background. One SQL file sets up the server side:
`supabase/migrations/20261118_account_features.sql` (paste into Supabase > SQL Editor once).

| Item | Decision | How |
| --- | --- | --- |
| 14.02 Sync | Opt-in, by button, never automatic. **Save to account** uploads the added agents and the settings file; **Get from account** replaces them here after a confirm, keeps a `.before-sync` copy, and never touches this computer's vault folder. No notes, no keys. | Table `sync_items`, one row per user and kind, only its owner can read or write it. |
| 14.03 Account page | `website/account.html`: sign in with Google, see name and plan, download, your share links, usage history, delete account. | supabase-js in the page, same project. |
| 14.04 Server features | Share links for one note, with a password and an expiry (1 minute to 24 hours), as `core/share.py` already planned. The link opens on the website; the password is checked on the server. | Table `shares`, functions `create_share`, `open_share`. Passwords are stored hashed (bcrypt). |
| 14.05 Plan | Two plans: **Free** (everything) and **Supporter** (a badge, same features). No payments in the beta; the owner marks a supporter by hand. | `app_metadata.plan`, which only the owner can change (see below). |
| 14.06 Abuse control | Hard limits in the database, not in the app: 20 live links and 50 new links a day per user, notes up to 200 KB, sync items up to 256 KB, a link locks after 10 wrong passwords. Sign-in rate limits are Supabase's own. | Checks inside the SQL functions and table constraints. |
| 14.07 Usage history | Opt-in ("Keep my usage history in my account", off by default). Sends one number per day: tokens used. No prompts, no agent names, no note names. | Table `usage_days`; sent when the user presses Save to account. |

Making someone a supporter (owner only, Supabase > SQL Editor):
`update auth.users set raw_app_meta_data = raw_app_meta_data || '{"plan":"supporter"}' where email = '<their email>';`
