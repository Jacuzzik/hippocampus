# Phase progress

The full list is in `PHASE.md` (427 items). This file records what each slice closed and how it was checked.
A row is "closed" only when a check proves it: a test, a lint rule, or a screenshot.

## Slices

| Slice | Commit | Items closed | Checks |
|---|---|---|---|
| Shared terminal | 48ee789 | 1.06, A.04 | e2e `terminal.spec.ts` |
| Planned cards | acdbec1 | 2.08, K.05, K.06, K.07, K.08, L.12 (part) | e2e `control.spec.ts` |
| Dead code out | dbd55ed | 1.23 (part), 4.13 (dropped: no phone or tablet layout) | npm test, e2e |
| Stability 2 | (this commit) | 1.04, 1.05, 11.02, B.02 (vault walked only after a change), 1.10, 5.01 (TALK opens the message box), 5.02 (32 px), 1.12, 5.05 (block tools asks first), 5.03 (IDE says why it is off), 6.07 (terminal font from the token), A.07 (feature switches), 11.09 (log file and viewer), F.03 (keys masked in logs), C.02, C.11 (.nvmrc) | pytest 303, npm test 73, ESLint 0, svelte-check 0, e2e 61 |
| Inbox | (next commit) | 9.01, 9.06 (one schema: act, work, replyTo, thread, priority), 9.02 (typed only when the terminal is quiet), 9.05 (live list, waiting badge), 9.07 (threads, filters), 9.08 (states and a reason for a failed message), 9.09 (acknowledgement-only dropped), 9.10 (loop guard), 9.11 (sender is the folder), 9.12 (compose box, one or all, urgent), 9.13 (monthly archive), 9.14 (search, export), 9.15 (tests), 8.04, 8.09 (format and example from the schema), L.18; also fixed: typed lines mixing in one input, task_send never worked, tests wrote to the real hive | pytest 330, npm test 73, ESLint 0, svelte-check 0, e2e 65 |

## Closed before this phase file existed (checked again this phase)

1.01, 1.02, 4.01, 4.02 (terminal garble: clean screenshot after the backend restart), 1.08, 5.04, 5.10, L.01, L.03, L.04, L.11 (one Tabs component), 1.15, A.02, D.02 (commits), 2.01, 2.10, C.08, C.09, C.10, D.04, D.05 (checks green on Node 24), 3.02 (colours in tokens), 6.01 to 6.06, 6.09, 6.10, D.08 (monospace token, font bundled), A.01, 2.05 (error boundaries and a global handler), A.03, B.03, 1.24 (one poll helper that pauses when hidden), A.08, A.10 (crash records, disk and memory warnings), M.06 (terminal text size saved), L.05, 3.10 (EmptyState), 7.01 (dropped by the plan).

## Needs the user

- D.10: what the scheduler's "obsidian" update should do; who "mr" and "hanis" are.
- 14.x and 15.x (account system and website): need a hosted sign-in provider, a domain and a security review. Not started.
- G.03, G.06: installers for Windows and macOS need those machines.
