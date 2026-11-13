# Phase progress

The full list is in `PHASE.md` (427 items). This file records what each slice closed and how it was checked.
A row is "closed" only when a check proves it: a test, a lint rule, or a screenshot.

## Slices

| Slice | Commit | Items closed | Checks |
|---|---|---|---|
| Shared terminal | 48ee789 | 1.06, A.04 | e2e `terminal.spec.ts` |
| Planned cards | acdbec1 | 2.08, K.05, K.06, K.07, K.08, L.12 (part) | e2e `control.spec.ts` |
| Dead code out | dbd55ed | 1.23 (part), 4.13 (dropped: no phone or tablet layout) | npm test, e2e |
| Stability 2 | 5a4617a | 1.04, 1.05, 11.02, B.02 (vault walked only after a change), 1.10, 5.01 (TALK opens the message box), 5.02 (32 px), 1.12, 5.05 (block tools asks first), 5.03 (IDE says why it is off), 6.07 (terminal font from the token), A.07 (feature switches), 11.09 (log file and viewer), F.03 (keys masked in logs), C.02, C.11 (.nvmrc) | pytest 303, npm test 73, ESLint 0, svelte-check 0, e2e 61 |
| Inbox | 08dec30 | 9.01, 9.06 (one schema: act, work, replyTo, thread, priority), 9.02 (typed only when the terminal is quiet), 9.05 (live list, waiting badge), 9.07 (threads, filters), 9.08 (states and a reason for a failed message), 9.09 (acknowledgement-only dropped), 9.10 (loop guard), 9.11 (sender is the folder), 9.12 (compose box, one or all, urgent), 9.13 (monthly archive), 9.14 (search, export), 9.15 (tests), 8.04, 8.09 (format and example from the schema), L.18; also fixed: typed lines mixing in one input, task_send never worked, tests wrote to the real hive | pytest 330, npm test 73, ESLint 0, svelte-check 0, e2e 65 |
| Shell and sandbox | d0b0731, e4efd60 | 10.01, 10.02, 10.03, 10.04, 10.05, 10.06, 10.07, 10.08, 10.09, 10.12, 10.13, F.01, F.02, 8.08 (limits computed from the switches). Off by default; only Claude Code runs in the sandbox. 10.10 open (Codex, Gemini, OpenCode not tested inside it). | pytest: 20 sandbox tests; real-path probe |
| Restart recovery | bb28fc9, 9b90c56 | A.06, 11.08 (the window starts the agents again after a backend restart), 2.11 (checked live) | e2e `terminal.spec.ts`; live restart |
| Briefing and traces | 46e171c | 8.01 (part: one module, generated parts), 8.06, 8.10 (version and hash, shown in INFO), 8.13 (lint stops a bad start), 8.16, 10.11, L.26 (Traces and Messages tabs are real), 1.03, 1.11 (cards and INFO show the agent's own status and context) | pytest 362, e2e 67 |
| Doctor and docs | 7a90d46, 19d33ac | 11.16 (Doctor page: what is set up and the next step for each gap), C.03, C.04 (ARCHITECTURE, SECURITY, CHANGELOG, release checklist) | pytest, e2e `settings.spec.ts` |
| CI green | dacbac7, 2ea74eb | D.05 (part): Rust format; tests no longer need bubblewrap or /proc; the terminal module loads on Windows; SQLite floor job pinned to ubuntu-24.04; Rust lint job gets a placeholder backend file | GitHub Actions run |
| Errors on screen | 2ea74eb | 2.04 (failed actions show a notice in the corner: once per problem, three at most, above every dialog), 2.06 (every backend failure has a message, a code and, when known, the next step; the window shows the next step), 2.07 (no panic on a failed start), 11.05 (unknown webhook kind is a clear error), 5.06 (text size 10 to 20, saved), 4.12 (one window title), 11.03 (.gitignore), 11.11 (terminal start is under one lock), 11.12 (keys in the system keychain), 1.07 (font from the token, bundled). Found by the new test: the test mock lacked `current_session`. | pytest 369, npm test 73, ESLint 0, svelte-check 0, e2e 70, clippy 0, screenshot |
| Layout | (this commit) | 4.03 (a long note title takes two lines and shows in full on hover; the column was already resizable), 4.04 (the graph controls have their own strip; names are drawn under it), 4.05 (note and link counts sit next to the agent cards; the cards already scroll), 4.07 (Stop has the red outline), 4.09 (ribbon icons have hover names and an 8 px rhythm), 4.10 (GRAPH caption removed), 4.11 (FREE, and one width per value) | e2e `layout.spec.ts` (73 pass), ESLint 0, svelte-check 0, screenshot |

## Closed before this phase file existed (checked again this phase)

1.01, 1.02, 4.01, 4.02 (terminal garble: clean screenshot after the backend restart), 1.08, 5.04, 5.10, L.01, L.03, L.04, L.11 (one Tabs component), 1.15, A.02, D.02 (commits), 2.01, 2.10, C.08, C.09, C.10, D.04, D.05 (checks green on Node 24), 3.02 (colours in tokens), 6.01 to 6.06, 6.09, 6.10, D.08 (monospace token, font bundled), A.01, 2.05 (error boundaries and a global handler), A.03, B.03, 1.24 (one poll helper that pauses when hidden), A.08, A.10 (crash records, disk and memory warnings), M.06 (terminal text size saved), L.05, 3.10 (EmptyState), 7.01 (dropped by the plan), 1.16 to 1.21 (fixed before the plan was written), 2.02, 2.03 (confirmations).

## Needs the user

- D.10: what the scheduler's "obsidian" update should do; who "mr" and "hanis" are.
- 14.x and 15.x (account system and website): need a hosted sign-in provider, a domain and a security review. Not started.
- G.03, G.06: installers for Windows and macOS need those machines.
