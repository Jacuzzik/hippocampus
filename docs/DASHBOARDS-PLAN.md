# Dashboards, top bar icons and one Settings window: plan

Asked for on 2026-11-16. Built one slice at a time, each with its own checks and commit, and a row in
`PHASE-progress.md` under the IDs below.

## What changes

1. **One Settings window (DB.01).** The Control panel goes away. Its five tabs become Settings pages:
   Overview, Work, Questions, Helpers and skills, Team and sharing. The ribbon button, the palette
   entry and every "open the Control panel" link open Settings on the matching page.
2. **Top bar icons (DB.02).** The bar above the graph gets four more icons next to Full screen:
   Dashboards, Add agent, Command palette, and a padlock that shows whether dashboards are locked.
3. **Dashboards (DB.03 to DB.09).** A full-window view opened from the top bar, the palette or
   `Ctrl+D`, with a list of dashboards on the left and tiles on the right.
4. **Dashboard lock (DB.03).** A switch in Settings > Dashboards. Locked: the tiles are read-only
   (no click, no typing, no keyboard focus) and a "Locked" badge shows. Unlocked: everything works.
   Picking another dashboard and closing the view work in both states. Default: locked.

## The ten dashboards

| # | Dashboard | Shows | Data from |
|---|---|---|---|
| 1 | Overview | agents running, tokens today, open tasks, questions waiting, system load | existing calls |
| 2 | Agents and spend | tokens today per agent, state, crashes | `budget`, `terminal_info` |
| 3 | Tasks | cards per column, waiting on you | `tasks` (read-only) |
| 4 | Notes | notes, links, orphans, top tags | `graph` |
| 5 | System | CPU, RAM, swap, disk, with a short history | `system_stats` |
| 6 | Activity | tool calls and approvals over the last day | `activity` |
| 7 | GitHub | open pull requests, open issues, newest CI runs of a repository | the `gh` tool |
| 8 | Calendar and scheduling | a month grid of scheduled jobs and your own events | `jobs`, a local events file |
| 9 | Phone | Android devices, start and stop screen mirroring (scrcpy opens its own window) | `adb`, `scrcpy` |
| 10 | Connected apps | one automatic dashboard per connected app | the app catalogue below |

## Connected apps (DB.06, DB.07)

A catalogue of 22 apps: Shopify, BuiltByBit, Stripe, GitHub, GitLab, Vercel, Netlify, Cloudflare,
Plausible, PostHog, Sentry, Airtable, Discord, Telegram, Lemon Squeezy, Gumroad, Paddle, WooCommerce,
Modrinth, Polar, YouTube, Todoist. (Linear and Notion were dropped: they cannot be read with GET.)

- Each app is one entry of data, not code: its address, how the key is sent, and a short list of
  numbers to read (a request path, where the number is in the answer, how to count it).
- Connect: paste the key (and a shop address where the app needs one) in Settings > Dashboards. The key
  goes to the system keychain, never to a file or a log. Disconnect removes it.
- A connected app gets a dashboard made from its entry: one tile per number, refreshed on open and on
  the Refresh button, never on a timer (the machine is weak).
- Requests are read-only (`GET`), have a time limit, and obey the app's network setting.

## Order of work

| ID | Slice | Checks |
|---|---|---|
| DB.01 | Control panel folded into Settings | Playwright (control, settings, dialogs, buttons, motion), visual baselines |
| DB.02 | Top bar icons | Playwright, visual baseline |
| DB.03 | Dashboards view, lock switch, Overview | Playwright incl. locked and unlocked |
| DB.04 | Agents and spend, Tasks, Notes, System, Activity | Playwright |
| DB.05 | GitHub dashboard | pytest with a fake `gh`, Playwright |
| DB.06 | App catalogue, connect and disconnect, keychain | pytest with a fake keychain and fake web answers |
| DB.07 | Automatic dashboard per connected app | pytest, Playwright |
| DB.08 | Calendar and scheduling | pytest, Playwright |
| DB.09 | Phone (scrcpy) | pytest with fake `adb` and `scrcpy`, Playwright |

## Limits known before building

- The 22 app entries are written from each app's public API documents and tested against fake answers
  only. None is checked against a real account until one is connected.
- scrcpy cannot draw inside the app window; it opens its own window.
- The Tasks dashboard stays read-only: the board belongs to the office, not to this app.

## State on 2026-11-17

All nine slices are built and committed. Still open:

- No app entry has been read with a real account. A made-up key was sent to each reachable service to
  confirm the address exists; BuiltByBit, Cloudflare and YouTube answered 400 and Telegram 404 to it,
  which fits a malformed key but does not prove the entry.
- Real phone mirroring was not started; only the device list was read with the real `adb`.
- The app has not been rebuilt or installed with any of this.
