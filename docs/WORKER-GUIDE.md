# Worker guide: finishing the Hippocampus phase

You are taking over a build that is partly done. Read this whole file once before you change anything.
It tells you what to do, in what order, how to check it, how to fix what breaks, and when to stop.

- **Repository:** `/home/thalha/hippocampus-worktrees/hippo-card-faces-kelly-match`
- **Branch:** `hippo-audit-fixes` (push here; never to `main`, never force-push)
- **Your list:** `docs/WORKER-OPEN-ITEMS.md` (220 of 427 plan items open when this was written)
- **Full wording of every item:** `docs/PLAN-text.txt` (search for the id at the start of a line, for example `^ *K.03`)
- **What is already done, and how it was checked:** `docs/PHASE-progress.md`
- **How the app is built:** `ARCHITECTURE.md`

---

## 1. The job in one paragraph

Hippocampus is a desktop app: a Tauri shell (Rust, `app/src-tauri`), a Svelte 5 window (`app/ui`), and a
Python backend (`core/`, `ai/`, `tools/`) that the shell starts as `python -m core serve`. A written plan lists
427 items. 207 are closed. You close the rest, one small slice at a time. A slice is closed only when a
check proves it: a test, a lint rule, or a screenshot you looked at. Your own opinion that it works is not a check.

---

## 2. Rules that are never broken

| Rule | Why |
|---|---|
| Never use `sudo`. Never type, store or repeat a password or a key. | The owner said so. Keys live in the system keychain only. |
| Never close or restart Munder Difflin (the other app on this computer). | It runs the owner's office. Only Hippocampus may be restarted. |
| Keep the computer light: one heavy command at a time, Playwright with `--workers=1`, Rust builds with `nice -n 15 ... -j 2`. | The machine is weak and has crashed before. |
| Never push to `main`. Never force-push. Never create a release or a tag. | Publishing is the owner's step. |
| Never deploy the website. Never build sign-in, sign-up or sync. | Blocked on the owner (section 12). |
| Never weaken a check to make it pass: no deleting a test, no `skip` without a real platform reason, no `# noqa` or `eslint-disable` to hide a real problem. | A green check that proves nothing is worse than a red one. |
| Never touch finished work except to fix a bug a check found (section 3). | Rework costs money and breaks what works. |
| Never write user-facing text with "sidecar". Say "backend". | The owner reads the screen, not the code. |
| No hard-coded colour, font or (new) pixel size in a component. Use tokens from `design/tokens.json`. | `npm test` fails the build on a raw colour or font. |
| Commit after every slice. End every commit message with the two attribution lines in section 10. | So nothing is lost and every change can be traced. |

---

## 3. Do not touch: finished work

These are done and checked. Do not rewrite, restyle, rename or "improve" them. If your slice needs one of them
to behave differently, stop and write the question in your report instead.

| Area | Files | Guarded by |
|---|---|---|
| Inbox and message delivery | `core/inbox.py`, `core/session_hive.py`, `app/ui/regions/InboxPanel.svelte` | `tests/core/test_inbox.py`, `e2e/inbox.spec.ts` |
| Shell sandbox | `core/sandbox.py`, `core/terminal.py` (`_sandboxed`, `sandbox_for`) | `tests/core/test_sandbox.py`, `test_agent_shell.py` |
| Briefings | `core/briefing.py` | `tests/core/test_briefing.py` |
| The one terminal component | `app/ui/regions/LiveTerminal.svelte` | `e2e/terminal.spec.ts` |
| Restart recovery | `app/ui/backend.svelte.ts`, restart effect in `LiveTerminal.svelte` | `e2e/terminal.spec.ts` |
| Error notices | `app/ui/notices.svelte.ts`, `app/ui/overlays/Notices.svelte`, `error_answer` in `core/__main__.py` | `e2e/notices.spec.ts`, `tests/core/test_error_answer.py` |
| Dialog keyboard focus | `app/ui/controls/dialogFocus.ts` | `e2e/dialogs.spec.ts` |
| Button audit | `e2e/buttons.spec.ts` | itself: it must keep passing as you add buttons |
| Themes and contrast | `design/tokens.json` (`color.semantic`, `color.light`), `app/scripts/contrast.test.mjs` | `npm test` |
| Motion rules | end of `app/ui/styles/global.css`, `duration` and `ease` tokens | `e2e/motion.spec.ts` |
| Loading placeholder | `app/ui/controls/Loading.svelte` | `e2e/loading.spec.ts` |
| Doctor and link doctor | `core/doctor.py`, `core/link_doctor.py` | `tests/core/test_doctor.py`, `test_link_doctor.py` |
| Settings export, import, safe writes | `core/safe_write.py`, `settings_export` / `settings_import` | `tests/core/test_settings_transfer.py` |
| CI and installer workflows | `.github/workflows/ci.yml`, `release.yml` | green runs on GitHub |
| Website | `website/` | not deployed; leave as is |

You **may** add to these files when a slice needs a new method, page or row. You may not change what is there.

---

## 4. Set up once per session

```bash
cd /home/thalha/hippocampus-worktrees/hippo-card-faces-kelly-match
git status --short            # must be empty before you start; if not, read section 11 "dirty tree"
git pull --ff-only            # stay current
source ~/.nvm/nvm.sh && nvm use 24     # Node 24 is required; do this in every new shell
uv run python scripts/open_items.py    # prints how many items are open
```

The app usually runs already in dev mode (`npm run tauri dev`, started from `app/`). Check with
`pgrep -af 'tauri dev|core serve'`. If it runs:

- A change in `app/ui` shows at once (hot reload).
- A change in Python needs a backend restart: `pkill -f 'python -m core serve'`. The app starts it again
  within about ten seconds, and every agent terminal restarts itself. This is allowed.
- A change in `app/src-tauri` makes the app rebuild and reopen on its own. Allowed, but do it rarely.

If it does not run, do not start it unless a slice needs a real-window screenshot; the Playwright tests
do not need it.

---

## 5. The loop for every slice

Do these six steps in order. Do not skip step 4. Do not start a second slice before the first is committed.

1. **Pick.** Take the next slice from section 7. A slice is 1 to 6 items that touch the same files.
2. **Read.** For each item, read its full text in `docs/PLAN-text.txt`. Then find the code with `rg`
   (search for a word from the item). Read only the files you will change and their tests.
3. **Check it is still open.** Many items were closed by other work and never recorded. Look at the code and
   the running tests first. If it is already true, go to step 5 and record it with the evidence
   ("already true: `path:line`" or the test name). Do not build it again.
4. **Build, then prove.** Make the smallest change that satisfies the item. Add or extend a test that would
   fail without your change. Then run the checks in section 6 that match what you touched.
5. **Record.** Add one row to the table in `docs/PHASE-progress.md` (above the line
   `## Closed before this phase file existed`): slice name, commit, the item ids with a few plain words
   each, and the checks with their numbers. Run `uv run python scripts/open_items.py`.
6. **Commit and push.** One commit per slice (section 10).

**Limits for one slice:** at most 5 passes of build-then-check. If two passes in a row change nothing
(same failure), stop that slice: revert it (`git checkout -- . && git clean -fd` inside the repo, only for
your own uncommitted work), write what you tried under "Found, not yet done" in `docs/PHASE-progress.md`,
and move to the next slice.

---

## 6. The checks: what to run, when, and what "pass" means

Run from the repository root unless a line says `app/`. Run the narrow check while you work and the full
set before you commit.

| You changed | Run | Pass means |
|---|---|---|
| Any Python | `uv run ruff check --fix . && uv run ruff format . && uv run pytest -q` | "All checks passed", then `N passed, 1 deselected`, 0 failed. N was 380 at handover and must not go down. |
| Any file in `app/` | in `app/`: `npx prettier --write ui e2e scripts && npx eslint . && npx svelte-check` | ESLint prints nothing; svelte-check ends `0 ERRORS 0 WARNINGS`. |
| `design/tokens.json` | in `app/`: `node scripts/build-tokens.mjs && npm test` | `pass 91` or more, `fail 0`. |
| Any UI behaviour | in `app/`: `npx playwright test --workers=1` (one file while working: `npx playwright test e2e/<file> --workers=1`) | `N passed`, 0 failed. N was 87 at handover and must not go down. |
| Rust | in `app/src-tauri`: `cargo fmt && nice -n 15 cargo clippy --locked -j 2 -- -D warnings` | "Finished", no warnings. |
| Anything a person sees | a screenshot you open and look at (below) | no overlap, no clipped text, no red notice, both themes if colours changed. |
| After a push | `gh run list --limit 3` a few minutes later | CI `success`. A `cancelled` run only means a newer push replaced it. |

**Screenshots.**

- Real window (only if the app is running): `grim /tmp/shot.png`, or a part: `grim -g "0,930 1000x150" /tmp/shot.png`. Then open the file and look.
- Any state you cannot reach by hand: a short Playwright script against the dev server, which uses the test mock:

```js
// app/shot.tmp.mjs  (delete it after use; never commit it)
import { chromium } from "@playwright/test";
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 860 } });
await page.addInitScript(() =>
  localStorage.setItem("hippocampus.prefs", JSON.stringify({ theme: "light", intro: "off" })),
);
await page.goto("http://127.0.0.1:1420/");
await page.waitForTimeout(2000);
await page.screenshot({ path: "/tmp/shot.png" });
await browser.close();
```

**A check you may not trust:** a test you wrote that passes on the first run. Break the code on purpose once
(or run the test before the change) and see it fail. A test that cannot fail checks nothing.

---

## 7. Order of work

Work the slices in this order. Each line says what to do and how to prove it. Item ids are in
`docs/WORKER-OPEN-ITEMS.md`.

### Stage A: record what is already true (cheap, do first)

Many open items are done in code but have no row in the progress file. For each id below, find the evidence,
and close it with "already true" plus the path or test. Build nothing unless the evidence is missing.

| Ids | Where to look for the evidence |
|---|---|
| 1.13, 1.14, 1.22, 2.12, 1.09 | read the item; check `app/vite.config.ts`, `core/terminal.py`, dialog titles |
| 12.01, 12.06, 12.08 to 12.11, 12.13, E.03 to E.05 | `app/ui/styles/global.css` (motion block), `e2e/motion.spec.ts`, `e2e/dialogs.spec.ts`, `e2e/buttons.spec.ts`. Build only what is truly absent and small. |
| 13.01 to 13.03, 13.06, 13.07 | `app/ui/overlays/LoadingScreen.svelte`, `app/ui/owner/bootTasks.svelte.ts`, `Loading.svelte` |
| L.02, L.07 to L.10, L.13 to L.28 | `app/ui/regions/RightPanel.svelte` and each `*Panel.svelte`; `e2e/right-panel-tabs.spec.ts` |
| M.01, M.03, M.04, M.07, M.10 to M.22, M.26, M.27, M.30 | `app/ui/control/SettingsDialog.svelte`, `app/ui/control/model.ts` (`SETTINGS_PAGES`), `ControlDialog.svelte` |
| G.01, G.02, G.04, G.05, I.01, I.02, I.04, C.05, C.07, A.09, B.01, D.03, D.07, D.09 | `README.md`, `RELEASE-CHECKLIST.md`, `.github/workflows/`, `app/ui/poll.ts` |
| J.01 to J.03, 9.04, 11.15, 2.02 | `app/ui/graph/`, `e2e/layout.spec.ts`, `core/session_hive.py` |

Expect about half of these to close with no code. What is left goes into the stages below.

### Stage B: finish the backend split (11.01, 11.04, 11.06, 11.07, 11.14)

- **11.01.** `core/__main__.py` is 1,476 lines. Move more method groups into `core/session_*.py` the same way
  the first four were moved: a plain class (`class NotesPart:`) holding the methods, added to the bases of
  `Session`. Good next groups: notes (`note_text` to `note_colour`), budget and network, memory, skills, agents.
  **Do not move** any method that uses a name a test patches on `core.__main__`: `build_router`, `get_api_key`,
  `set_api_key`, `clear_api_key`, `HIVE_DIR`, `SETTINGS_PATH`, `SKILLS_DIR`. Check with
  `rg "setattr\(sidecar" tests`. Target: under 900 lines. Proof: `uv run pytest -q` still 380 or more, and
  `echo '{"id":1,"method":"system"}' | uv run python -m core serve --storage /tmp/hippo-check | tail -1`
  prints a `result`. Then lower the number in `test_no_backend_file_grows_past_1500_lines` to 1000.
- **11.04, 11.06.** For each backend method with no caller in `app/ui` (`rg '"method": "x"\|method: "x"' app/ui`),
  either wire it or delete it with its test. A method that needs something not installed must raise
  `NotSetUp` (its hint is added for you by `ERROR_HINTS`).
- **11.07.** One table `METHODS` in a new `core/methods.py`: name, the keys it needs, one line of help. Make
  `dispatch` refuse an unknown method or a missing key from that table. Test: every name in the dispatch
  tables is in `METHODS` and the reverse.
- **11.14.** A `data_version` file in the storage folder; a `migrate(storage)` function called at start that
  copies the folder to `backups/` before any change. Test with a temporary folder.

### Stage C: shared controls (3.04, 3.07, 3.08, 5.09, 5.11, 5.13, 4.06, 4.08, 3.03, 3.05)

- Create `app/ui/controls/Button.svelte` with `variant` (`primary`, `secondary`, `danger`, `ghost`) and `size`
  (`sm`, `md`). Sizes and colours come from tokens. Replace buttons **one component file per commit**, starting
  with dialogs. After each file run the Playwright tests: the names of buttons must not change.
- Create `app/ui/controls/Toggle.svelte` (5.09) and use it for the graph's two switches and the Settings switches.
- Create `app/ui/controls/PanelHeader.svelte` (3.07) and use it in the eight `*Panel.svelte` files.
- 3.08: move the scrim, box, title and close button of the dialogs into `app/ui/controls/Dialog.svelte`. Keep
  `use:dialogFocus` inside it. Convert one dialog per commit.
- Proof for all: `e2e/buttons.spec.ts`, `e2e/dialogs.spec.ts` pass; screenshots in both themes.

### Stage D: Control Room tabs and panels (what Stage A left of L.x, plus B.04, B.05)

- L.06: keep heavy panes mounted (hide with the `hidden` attribute) instead of an `{#if}` chain, so a tab change
  does not reload them. The terminal already works this way; copy it.
- L.08: unread and waiting counts on tab labels, from the data the panels already load.
- B.04: only if a list can pass 500 rows; otherwise close as "not needed yet" with the reason.
- Proof: `e2e/right-panel-tabs.spec.ts` plus a new test per behaviour.

### Stage E: Settings (what Stage A left of M.x)

- M.27: one schema list in the backend (`key`, `type`, `default`, `help`) used by `load_settings` and returned
  by the `settings` method; a test that every key in the file is in the schema.
- M.10: one `SettingRow.svelte` and use it for every row.
- Each new setting: backend save function in `core/settings.py` (copy `save_agent_shell`), a method, a row, a
  mock case in `app/e2e/tauri-mock.ts`, a pytest and a Playwright test.

### Stage F: connectors (K.x)

Read K.21 first: a connector that cannot run yet is still a real card that says why. Never show a connector as
working unless a test call succeeded.

1. K.11: `core/connectors.py` with a registry: id, name, state (`Not connected`, `Connected`, `Needs setup`,
   `Error`), what it needs. Method `connectors`. Test: every connector has all fields.
2. K.12: cards in Settings, Connectors read from that method (replace the hard-coded list).
3. K.03, K.17: read MCP servers from the CLI config files on disk (`~/.claude.json`, project `.mcp.json`).
   Read only. Never print a token: show names and commands with values masked.
4. K.10, K.20: Ollama card: call `GET {host}/api/tags` with a 3 second limit; show reachable or not and the models.
5. K.09, K.18: GitHub card from `gh auth status` (10 second limit).
6. K.04, K.14: webhook add, edit, remove forms on the existing `save_webhook` / `delete_webhook` methods.
7. K.13, K.16, K.19, K.25: cards only, state `Needs setup`, with the reason. Do not build Slack, Notion,
   Calendar, Gmail or Drive calls.
8. K.22 to K.24, K.26: log each connect and test in the activity journal (`self.note("setting", ...)`); tests
   with a fake local server.

### Stage G: features (7.x and N.x)

Do these last. For each: read the item, decide **build** (small, local, no new service) or **card** (a
`StatusCard` with `status="Planned"` and the honest reason, as in `SettingsDialog.svelte`). Record which.

Build (small and local): N.13 spend meter in the top bar (data from `budget`), N.14 focus mode, N.23 pinned
notes per agent, N.24 quiet mode, N.25 and J.04 graph export to PNG (draw then `canvas.toBlob`, save through a
new backend method into the vault's `exports/` folder), N.19 unsent message kept in `localStorage`,
N.18 folder warnings in Doctor, 7.14 per-agent log filter, 7.17 skill search, 7.29 first-run wizard using Doctor.

Card only (needs a service, a model download, or a large design): 7.06, 7.09, 7.11, 7.18, 7.21, 7.25, 7.27,
7.30, 7.31, N.01, N.09, N.11, N.17, N.21, N.22, H.02, H.03.

Anything not named: default to **card** unless it is under 150 lines of new code.

### Stage H: leftovers

3.11, 3.12, 3.15, 4.14 to 4.16, 5.08, 5.12, 5.14, 6.14, 6.16, 6.18, 8.02 to 8.15, B.06, F.06, H.01, H.04.
For briefings (8.x): only add; `core/briefing.py` has a lint (`briefing.lint`) and a version number
(`VERSION`). Any change to briefing text must raise `VERSION` by one and keep `test_briefing.py` green.

---

## 8. How to add things (copy these patterns)

**A backend method**

1. Write it as a method of a part class in `core/session_<area>.py` (or `Session` in `core/__main__.py`).
   No argument: `def thing(self) -> dict[str, Any]`. With input: `def thing(self, request: dict[str, Any])`.
2. Register it in `Session.dispatch`: the `simple` table for no-argument methods, the `extra` table for
   methods that take `request`.
3. Bad input raises `ValueError("plain sentence saying what is needed")`. The window shows that sentence.
4. Test in `tests/core/test_<area>.py`. Build a session with
   `Session(storage=tmp_path / "storage", settings=Settings(), settings_path=tmp_path / "settings.toml")`.
   Tests never touch the real hive: `conftest.py` redirects it.
5. Writing a file: `safe_write.write_text(path, text)`. Running a program: always pass `timeout=`.

**A call from the window**

```ts
const found = await invoke<{ rows: Row[] }>("sidecar_call", { method: "thing", params: { id } });
```

- A read that fills a panel: keep `failed` and `loaded` flags and show `<Loading what="the things" />`
  until the first answer (copy `app/ui/regions/SkillsPanel.svelte`).
- An action the user started: on failure call `report("Could not save the thing", cause)` from
  `app/ui/notices.svelte.ts`. The sentence has no full stop; the notice adds it.
- Add the same method to the mock in `app/e2e/tauri-mock.ts` (a `case "thing":` in the big switch), or every
  Playwright test that opens that screen shows a red notice and `e2e/notices.spec.ts` fails.

**A Settings page:** add it to `SETTINGS_PAGES` in `app/ui/control/model.ts` (with search words), add an
`{:else if page === "Name"}` block in `SettingsDialog.svelte`, and add `Name: "text on that page"` to the
page table at the top of `e2e/settings.spec.ts`.

**A colour, size or duration:** add it to `design/tokens.json`, run `node scripts/build-tokens.mjs` in `app/`.
A new colour that differs in the light theme also goes under `color.light`, and into the pairs in
`app/scripts/contrast.test.mjs` if text is drawn with it.

**A dialog:** `role="dialog"`, `aria-modal="true"`, a name, `tabindex="-1"`, `use:dialogFocus`, and Escape
closes it with `e.stopPropagation()`.

**A keyboard shortcut:** add the handler, and add a row to `app/ui/shortcuts.ts` (Settings, Keyboard reads it).

---

## 9. How to close an item

An item is closed when its id appears in a row of `docs/PHASE-progress.md`. Write the row like the existing ones:

```
| Slice name | <commit> | K.11 (one connector registry in the backend), K.12 (cards read it) | pytest 384, e2e 89, ESLint 0, svelte-check 0, screenshot |
```

- Say what is true now in plain words, not what you did.
- "part" after an id means not finished: say what is left in the same cell. A "part" id still counts as
  closed by the script, so also add the leftover under `## Found, not yet done`.
- A dropped item: write "(dropped: reason)". Only the plan or the owner can drop an item, not you. The owner
  has dropped: phone and tablet layouts, and D.10.
- Then run `uv run python scripts/open_items.py` and commit the regenerated list with the slice.

---

## 10. Commits

```bash
git add -A
git commit -m "Plain sentence saying what is true now

Optional second paragraph: why, in one or two lines.

Co-Authored-By: Claude <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01UXjtzdnGwSbF1GzGT7nRoG"
git push
```

- One slice, one commit. Never commit a failing check. Never commit `*.tmp.mjs`, `test-results/`, screenshots.
- Use the attribution lines your own session gives you if they differ from the two above.

---

## 11. When something breaks: the fix for each known failure

| What you see | Cause | Fix |
|---|---|---|
| `npm` or `npx` fails oddly, or a syntax error in a config file | wrong Node | `source ~/.nvm/nvm.sh && nvm use 24` |
| Playwright: `Port 1420 is already in use` | the dev server runs; fine | nothing: the tests reuse it |
| Playwright: a test times out on a click, log says `scrim ... intercepts pointer events` | a dialog is open over the target | close the dialog first (its close button), or raise the target's layer if it must be clickable over dialogs (notices use `z-index: 90`) |
| Playwright: `strict mode violation ... resolved to 2 elements` | two elements share the name | narrow the locator (`dialog.getByRole(...)`, `.first()`) |
| A red notice "mock: unknown method x" in a test or screenshot | the mock lacks the method | add `case "x":` to `app/e2e/tauri-mock.ts` |
| `getByLabel("...")` stops finding a field | an `aria-label` was added and now overrides its `<label>` | remove the `aria-label` |
| ESLint `Forbidden non-null assertion` | `x!` | check for null and throw a clear error |
| ESLint `'_' is defined but never used` in an `{#each}` | unused loop variable | loop over `[...Array(n).keys()]` |
| svelte-check `Do not use empty rulesets` | a CSS rule lost its last line | delete the empty rule |
| `npm test`: "UI source has no hardcoded colors" | a `#hex` or `rgb()` in a component | add a token and use `var(--color-...)` |
| `npm test`: a contrast line `x on y is 4.3:1` | colour too light or dark | change the token until it is 4.5:1 or more; do not remove the pair |
| pytest: `module 'core.__main__' has no attribute X` | you moved a name tests read | import it in the test from its new module |
| pytest fails only after moving methods, in a test that patches `sidecar.<name>` | the moved code reads the name from its new module, not the patched one | move that method back |
| ruff: `F821 Undefined name` after a move | a helper stayed behind | move the helper with its users |
| CI fails on Windows with `No module named fcntl` / `termios` / `pty` | Unix-only import at module top | guard the import (`try ... except ImportError`), and `pytest.importorskip` in the test |
| CI fails on Windows with `WinError 32` | a file is deleted while still open | close it first (see `Store._connect`), or skip the test on `win32` only if it tests deleting an open file |
| CI fails on macOS: `/proc/...` or `bwrap is not installed` | Linux-only feature in a test | mock `shutil.which`, or mark the test `skipif(sys.platform != "linux")` with the reason |
| CI Rust job: `resource path binaries/hippocampus-sidecar-... doesn't exist` | the placeholder step was removed | keep the "Placeholder for the bundled backend" step in `ci.yml` |
| CI: Prettier lists a file | not formatted | `npx prettier --write .` in `app/` |
| The agent terminal in the real app is blank or garbled after your change | the backend restarted and the window did not follow | you broke the restart effect in `LiveTerminal.svelte`: revert your change to that file |
| **Dirty tree** at session start (`git status` not empty) | a previous session stopped mid-slice | run the full checks; if they pass, finish and commit that slice; if not, `git stash` and report it. Never delete someone else's work. |
| `git pull` refuses | the branch moved | `git pull --rebase`; if it conflicts, stop and report |
| The same failure after two different fixes | you do not understand the cause yet | stop guessing: read the failing test and the code it calls, top to bottom, before the next change |

---

## 12. When to stop and ask the owner

Stop the slice, leave the code working, and write the question in your final report when:

- An item needs a new account, a paid service, a domain, a credential, or anything published.
  This covers all of **14.x**, website pages **15.03 and 15.04**, **15.08 to 15.11**, deploying `website/`,
  creating a release, and testing installers by hand on Windows or macOS (**G.03, G.06**: the installers
  build on GitHub; nobody has installed one).
  Owner decisions on 2026-11-13: sign-in will be **Google account sign-in**, but it stays blocked until
  the owner supplies a Google OAuth client ID and a domain; Windows and macOS installer testing is
  **on hold**, so skip G.03 and G.06 without asking.
- Two items contradict each other, or an item contradicts section 2 or 3.
- A fix would need deleting user data, changing the vault's notes, or changing how keys are stored.
- You would have to change a file in section 3 beyond adding to it.

Do not stop for: which of two reasonable designs to pick (pick the smaller one and say so), a failing check
you can fix, or an item that turns out to be already done.

---

## 13. What to report at the end of each session

Keep it short and factual:

1. Open count before and after (`uv run python scripts/open_items.py`).
2. Slices committed: name, commit, item ids.
3. Last check numbers: pytest passed, npm test pass, Playwright passed, CI state of the last push.
4. What you checked only partly, and how (for example "light theme checked in browser screenshots, not in the real window").
5. Slices you gave up on, with what you tried.
6. Questions for the owner (section 12), one line each.

Never write "done" for something no check proved. If a test failed, say so and paste the failing line.
