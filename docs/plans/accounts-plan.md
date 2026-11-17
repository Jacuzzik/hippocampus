# Accounts plan (draft for the owner)

Status: **draft, not agreed.** No account code gets written until the owner signs off on the decisions at the end.
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
