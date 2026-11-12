# Hippocampus: the complete phase

Source: `Hippocampus-Audit-and-Plan.pdf` text, all 427 unique item rows (numbered 1.01 to 15.12, lettered A to N). Status is from the plan as written, plus what this session checked. Nothing below has been started in this phase yet.

## Counts

- Open fixes (needs fixing): 156
- Confirmations, no action: 7
- Features (section 7 table and section N): 61
- Planned (proposals, not built): 187
- Decisions and work items (D rows): 10
- Already fixed in the plan: 6

## Phase order

Taken from the plan's order of work. Each step ends with its checks passing (pytest, npm test, ESLint, svelte-check, Playwright, screenshot). Stop after 5 passes per slice or two passes with no change.

1. Stability: error boundary, sidecar watchdog, one terminal component, timers (A, B)
2. Terminal garble and the input line (1.01, 1.02, 4.01, 4.02), then fonts (6.x, D.08)
3. Tokens and shared components: colours, sizes, Button, Dialog, PanelHeader, Tab, EmptyState (3.x, 5.x, 4.x, K, L, M components)
4. Backend cleaning: split core/__main__.py, logging, error envelope, supervised sidecar, indexer debounce (11.x)
5. Inbox and briefings together, one message schema (8.x, 9.x)
6. Shell for all agents with the bwrap sandbox, tested before it is turned on (10.x, F.01, F.02)
7. Motion and loading states (12.x, 13.x, E.x)
8. Munder Difflin feature set in plan order, then section N features (7.x, N.x)
9. Settings and Control panel: one schema, Operations (M.x, L.x)
10. Connectors: registry and cards, then Slack, webhooks, missions, MCP, GitHub (K.x)
11. Account system and website last, after a security review (14.x, 15.x)
12. Release: Node 24 tests, screenshots, clean-machine install, tag, push, launch (C, D, G, I)

## 1. Needs fixing (156)

### P0 (9)

- **1.01** FOUND | P0 | Agent side-panel terminal (wdwdw) is garbled: | Send the CLI a correct  
  _Status: LIKELY FIXED: screenshot after backend restart is clean; confirm with a fresh screenshot_
- **1.02** FOUND | P0 | The bottom Remote Control / input line of the agent | Make the .screen box and  
  _Status: LIKELY FIXED: last line visible in screenshot; confirm_
- **4.01** FOUND | P0 | Agent terminal text overlaps and drops characters. | See section 1.  
  _Status: LIKELY FIXED: same as 1.01_
- **4.02** FOUND | P0 | The last terminal line (Remote Control / input) is | See section 1.  
  _Status: LIKELY FIXED: same as 1.02_
- **6.01** FOUND | P0 | The sans-serif UI font is defined once: --font-ui is | Point --font-ui at the
- **6.02** FOUND | P0 | The page body uses --font-ui. | Body uses the monospace
- **6.09** FOUND | P0 | No monospace font is bundled and JetBrains Mono is | Bundle JetBrains Mono
- **10.01** FOUND | P0 | Normal agents are blocked from Bash entirely: 'Bash' | Replace with the policy
- **A.01** FOUND | P0 | No UI crash guard: no error boundary, no global | Add a root error

### P1 (58)

- **1.03** FOUND | P1 | Every added-agent card shows the assistant's orb | Read the status from the
- **1.04** FOUND | P1 | Seven panels load once and go stale: ActivityPanel | One shared refresh
- **1.05** FOUND | P1 | The vault indexer re-syncs about every 5 seconds | Sync only on file-system
- **1.06** FOUND | P1 | The main terminal and the side-panel terminal size | One shared terminal  
  _Status: CLOSED this session: one terminal component (48ee789)_
- **1.07** FOUND | P1 | Terminal font is hard-coded to 'JetBrains Mono'. | Bundle JetBrains Mono
- **2.01** FOUND | P1 | JavaScript tests cannot run on this machine: they | Install Node 24 (nvm  
  _Status: CLOSED: JS tests run on Node 24 (npm test 73/73)_
- **2.04** FOUND | P1 | The UI shows errors almost nowhere: 31 console.error | One error banner / toast  
  _Status: PARTLY: crash log and health warnings added (3540ccf)_
- **2.05** FOUND | P1 | No global error handler exists in the UI. | Add window error +  
  _Status: PARTLY: crash log records window errors (3540ccf)_
- **2.09** AUDIT | P1 | Chat fails with no Claude key and no Ollama | First-run screen that
- **2.10** VERIFY | P1 | svelte-check (npm run check) and ESLint (npm run | Run both on Node 24 and  
  _Status: CLOSED: svelte-check 0 errors, ESLint 0 errors_
- **2.11** VERIFY | P1 | Crash behaviour of the sidecar and PTY pump thread | Kill the sidecar in a
- **3.01** FOUND | P1 | Only one theme exists: no prefers-color-scheme or | Define light and dark
- **3.02** FOUND | P1 | Colours are hard-coded outside the tokens: 11 hex | Move every colour into
- **3.03** FOUND | P1 | 54 fixed pixel width / height / min / max | Replace with tokens or
- **3.04** FOUND | P1 | Buttons have no shared component: 17 separate button | One Button, IconButton,
- **4.03** FOUND | P1 | Left note list cuts titles with an ellipsis: 'Test | Tooltip on hover; allow
- **4.04** FOUND | P1 | A graph node label ('Test Meeting: Q4 onboarding | Reserve a toolbar band;
- **4.05** FOUND | P1 | The bottom agent bar uses about a third of the | Wrap cards in a scroll
- **4.06** FOUND | P1 | The right panel stacks four different grid patterns: | One action row with
- **5.01** FOUND | P1 | TALK is disabled on both card types and has a 10 px | Remove, or build voice
- **5.02** FOUND | P1 | TALK and INFO are about 25 px tall on the 1920 x | Minimum 32 px height, 36
- **6.03** FOUND | P1 | office-theme.css sets --font-ui in three places. | Switch to the monospace
- **6.04** FOUND | P1 | Left / right sidebars and panels: TempsPanel:41, | Remove the local font-
- **6.05** FOUND | P1 | Cards and bottom bar: seven declarations in | Same.
- **6.06** FOUND | P1 | Agent panel and dialogs: AgentPanel:285 and :353, | Same.
- **6.07** FOUND | P1 | The terminal hard-codes 'JetBrains Mono, monospace' | Read the token with
- **6.08** FOUND | P1 | The ASCII graph renderer sets a literal 'monospace' | Use the token.
- **6.11** VERIFY | P1 | Form controls (button, input, select, textarea) do | Add button, input,
- **6.12** VERIFY | P1 | Native select menus are drawn by the OS in the | Use the Dropdown
- **8.01** FOUND | P1 | A briefing is one free-form markdown file per agent. | Replace with a
- **8.02** FOUND | P1 | Delivery differs by CLI: Claude reads it as a | One tested delivery path
- **8.03** FOUND | P1 | The typed pointer waits a fixed 6 s (up to 60 s) | Wait for the CLI prompt
- **9.01** FOUND | P1 | Messages carry only id, from, to, subject, body and | Add act, work, replyTo,
- **9.02** FOUND | P1 | The app types a received message into the receiver's | Deliver by a short 'new
- **9.05** FOUND | P1 | InboxPanel loads once and has no unread counts. | Live list, unread badge
- **10.02** FOUND | P1 | The main agent has a fenced shell: rm, rmdir, mv, | Keep these as the deny
- **10.03** FOUND | P1 | The code says the fence is best effort: a shell can | Add an OS-level sandbox.
- **10.04** FOUND | P1 | Every agent is already denied Read and Edit under | Keep; this is the app-
- **11.01** FOUND | P1 | core/__main__.py is 1,564 lines; the next file is | Split by domain: chat,
- **11.02** FOUND | P1 | The vault indexer runs about every 5 s with no | Debounced file watcher
- **12.01** FOUND | P1 | Motion exists only in LoadingScreen, Orb and | Add motion to all other
- **13.01** FOUND | P1 | Start-up loading screen and a boot-task counter | Commit them; they are
- **A.02** FOUND | P1 | One uncommitted working tree holds several features, | Work in small commits on  
  _Status: CLOSED: working tree clean, committed in slices_
- **A.03** FOUND | P1 | Ten timers poll the sidecar every 1-5 s. | Share one scheduler;
- **A.04** FOUND | P1 | Terminal sizing code differs between two components. | One component.  
  _Status: CLOSED this session: one terminal component (48ee789)_
- **B.01** FOUND | P1 | Ten polling timers at five different intervals: 1 s | Replace with events
- **B.02** FOUND | P1 | The vault index re-runs every 5 s with no changes. | Content-hash cache.
- **C.02** FOUND | P1 | JS tests need Node 24; the shell has Node 20.20.2. | Add .nvmrc and a CI  
  _Status: PARTLY: Node 24 used; .nvmrc not added_
- **C.08** FOUND | P1 | JS tests on Node 24.22.3: 73 tests, 72 pass, 1 | Move colours to tokens  
  _Status: CLOSED: npm test passes on Node 24_
- **F.01** FOUND | P1 | Pattern-based shell fences are bypassable; the code | Use the bwrap sandbox
- **K.01** FOUND | P1 | Settings > Integrations is the keys list plus one | Replace with connector
- **K.02** FOUND | P1 | API keys for 14 model providers sit under | Split into 'Models and
- **K.03** FOUND | P1 | MCP servers and Plugins lists are hard-coded empty | Read the CLI config
- **L.01** FOUND | P1 | Control Room has 11 tabs in three pills of 4, 4 and | One Tab component;
- **L.03** FOUND | P1 | The Settings tabs set tabindex to 0 for the selected | Roving focus with arrow
- **M.01** FOUND | P1 | The Control panel is one scrolling list of 15 | Split into Operations
- **M.02** FOUND | P1 | Settings has six tabs, but the General tab has no | Fill with real controls
- **M.03** FOUND | P1 | NetworkSection, BudgetSection, KeysSection and | One home per setting.

### P2 (89)

- **1.08** FOUND | P2 | Git tab has aria-selected hard-coded to 'false', so | Bind it to the view
- **1.09** FOUND | P2 | The panel size is ignored while the panel is under | Resend the size when the
- **1.10** FOUND | P2 | TALK is permanently disabled on every card. | Implement voice or
- **1.11** FOUND | P2 | Context bar shows a dash when no value arrives, for | Wire a value for every
- **1.12** FOUND | P2 | Toggling Block tools stops and restarts the agent | Ask for confirmation and
- **1.13** FOUND | P2 | Dialog title and entry point use different names: | Pick one name.
- **1.14** FOUND | P2 | Dev server uses a strict port (1420): a second start | Fail with a clear
- **1.15** FOUND | P2 | 13 uncommitted entries, including two untracked | Commit in small slices;
- **1.22** AUDIT | P2 | 'OpenAI' API-key provider runs the Codex CLI and | Re-check; either run the
- **1.23** AUDIT | P2 | Four components are mounted nowhere: OwnerPanel, | Confirm by import  
  _Status: PARTLY: Orb and AgentCard removed (dbd55ed); others still to check_
- **1.24** VERIFY | P2 | Timer clean-up: App.svelte, GraphPanel, GraphRegion, | Confirm each timer is
- **2.06** FOUND | P2 | Backend raises useful sentences that the UI does not | Return {code, message,
- **2.07** FOUND | P2 | The Rust side has one unwrap/expect/panic call. | Find it and return a
- **2.08** AUDIT | P2 | Share and Teams fail with fixed messages: 'No share | Hide or label these  
  _Status: CLOSED: Share and Teams are Planned cards (acdbec1)_
- **2.12** FOUND | P2 | Terminal size errors surface as garbled output | Treat a size mismatch as
- **3.05** FOUND | P2 | Three global stylesheets plus per-component CSS | One token file, one
- **3.06** FOUND | P2 | The smallest text token is 10 px and is used for | Raise the minimum UI
- **3.07** FOUND | P2 | Every panel redeclares its own heading font and | Shared PanelHeader and
- **3.08** FOUND | P2 | Dialogs differ: AddAgentDialog, SettingsDialog, | One Dialog shell: title
- **3.09** FOUND | P2 | Graph colours live in their own file, not the | Read from tokens so
- **3.10** FOUND | P2 | Empty or missing data is a dash, not a designed | Empty-state component
- **4.07** FOUND | P2 | Stop (a destructive action) and Block tools (a | Give destructive actions
- **4.08** FOUND | P2 | Gaps are tight in the terminal area and loose in the | Use spacing tokens for
- **4.09** FOUND | P2 | The left ribbon has four unlabelled icons with | Add labels on hover and
- **4.10** FOUND | P2 | The 'GRAPH' caption bottom-left is very small and | Merge into the graph
- **4.11** FOUND | P2 | The top stats bar (CPU, RAM, SWAP, DISK, DISK FREE) | Shorter labels and
- **4.12** VERIFY | P2 | Window title shows 'hippocampus' and 'Hippocampus' | Check tauri.conf title
- **4.13** VERIFY | P2 | Behaviour at narrow window widths is not tested. | Set a minimum window
- **4.14** VERIFY | P2 | Dialog placement and button order (Save / Cancel) in | Add them to the
- **5.03** FOUND | P2 | IDE is disabled without a folder and gives no | Add a title: 'Set an
- **5.04** FOUND | P2 | Git tab is disabled without a folder, no reason, and | Same title and bind
- **5.05** FOUND | P2 | Block tools restarts the session without a | Confirm dialog.
- **5.06** FOUND | P2 | Text size buttons: minimum 9, no maximum, not | Clamp 10-20; store in
- **5.07** FOUND | P2 | Send is disabled when empty (good) but there is no | Placeholder hint and a
- **5.08** FOUND | P2 | + files is the only attach path; files over 100 KB | Drag-and-drop, progress,
- **5.09** FOUND | P2 | Graph toolbar mixes one button (Fit graph) with two | Toggle component with
- **5.10** FOUND | P2 | Tabs (terminal / git / messages / traces) share one | One tab component with
- **5.11** FOUND | P2 | 17 button rule blocks mean 17 sizes and radii. | Replace with one
- **5.12** FOUND | P2 | Icon-only buttons rely on title; aria-labels exist | Keep; add visible
- **6.10** FOUND | P2 | Inter is also not bundled, so today the UI font | Removed by this change.
- **6.13** VERIFY | P2 | Canvas and constellation graph renderers draw | Search for fillText
- **8.04** FOUND | P2 | The start-up inbox is a second separate file the | Embed the inbox summary
- **8.05** FOUND | P2 | The reference system uses a contract per task | Use the same four parts
- **8.06** VERIFY | P2 | The Goal field is required in Add Agent and used for | Trace goal to briefing
- **9.03** FOUND | P2 | Writes are atomic (temp file then rename), which is | Keep.
- **9.04** FOUND | P2 | Outbox collection exists, but its trigger and | Run on file events plus
- **9.06** FOUND | P2 | The reference system defines message acts: request, | Adopt the same set so
- **10.05** FOUND | P2 | Block tools stays as an opt-in that removes shell, | Keep for review-only
- **11.03** FOUND | P2 | Backups and graph output sit untracked in the repo | Add to .gitignore;
- **11.04** AUDIT | P2 | Backend methods with no UI: open, webhook save / | Re-check each; wire or
- **11.05** AUDIT | P2 | run_webhook raises KeyError on an unknown kind. | Return a clear error.
- **11.06** AUDIT | P2 | Memory search raises NotSetUp; share_note always | Gate the UI on a
- **12.02** FOUND | P2 | Only 3 prefers-reduced-motion rules exist. | Every new motion is
- **13.02** FOUND | P2 | The components make 21 direct sidecar calls; which | List every call and give
- **C.03** FOUND | P2 | UI tests cover models and tokens only (graph, | Add component and end-
- **C.09** FOUND | P2 | ESLint reports 4 errors: graph-model.test.mjs has | Fix all four; lint must  
  _Status: CLOSED: ESLint 0 errors_
- **C.11** FOUND | P2 | Node 20.20.2 was the default shell version and | Add .nvmrc with 24 so
- **E.01** FOUND | P2 | Reduced-motion is handled in only 3 places. | Wrap all motion.
- **E.02** FOUND | P2 | 10 px labels are below a readable minimum. | 12 px minimum.
- **E.03** FOUND | P2 | Some buttons have aria-pressed and aria-label; tabs | Audit all roles.
- **F.02** FOUND | P2 | The app is denied to agents via path rules for Read | Add a test that proves
- **G.01** FOUND | P2 | A release build output exists under src- | Confirm what the
- **G.02** FOUND | P2 | Dev mode needs Vite on a fixed port plus the Tauri | Document it in the
- **H.01** VERIFY | P2 | Whether Hippocampus has any message catalogue is | Read the 5 files.
- **I.01** FOUND | P2 | The reference project has README, CHANGELOG, | Use as a checklist.
- **I.02** FOUND | P2 | Hippocampus root has README, CONTRIBUTING, | Fill the gaps.
- **J.02** FOUND | P2 | Graph label collides with the toolbar. | Clamp labels.
- **J.03** FOUND | P2 | Graph Theme and Personal board buttons were listed | Re-check and remove dead
- **K.04** FOUND | P2 | Webhooks are local only: core/webhooks.py says | Add form and a real
- **K.05** FOUND | P2 | Share by password link shows a 'Not set up' badge. | Real feature or hide;  
  _Status: CLOSED: Share is a Planned card (acdbec1)_
- **K.06** FOUND | P2 | Teams section is one 'Not set up' sentence (needs a | Placeholder card with  
  _Status: CLOSED: Teams is a Planned card (acdbec1)_
- **K.07** FOUND | P2 | Dispatch lists 'Assistant (Not set up)' as a target | Disable with a visible  
  _Status: CLOSED: Assistant shows as planned (acdbec1)_
- **K.08** FOUND | P2 | Context compaction is 'Not set up'. | Daily compact exists in  
  _Status: CLOSED: context compaction is a Planned card (acdbec1)_
- **K.09** FOUND | P2 | GitHub issues reach the Monitor pane only through | GitHub connector card
- **K.10** FOUND | P2 | Local model (Ollama) check is 'Not set up: this | Real check: reachable,
- **K.27** VERIFY | P2 | Which of these connectors are Pro-only in the | Check the reference repo
- **L.02** FOUND | P2 | A comment says 'Only the terminal is built; the rest | Fix the comment; decide
- **L.04** FOUND | P2 | Control Room tab buttons have role=tab but no aria- | Wire aria-controls and
- **L.05** FOUND | P2 | Empty states are one muted line each: 'No messages | One EmptyState
- **L.06** FOUND | P2 | Tabs unmount when you leave them (an if-chain), so | Keep the heavy panes
- **L.07** FOUND | P2 | 'ask me' and 'triggers' render the same sections | One home per feature
- **L.08** FOUND | P2 | Tab labels are raw lowercase words with no icon, no | Badges: unread, pending,
- **L.09** FOUND | P2 | The Monitor pane's engine line is documented as | Wire the switch or fix
- **L.10** VERIFY | P2 | Whether the four ribbon icon buttons show a tooltip | Check in a screenshot.
- **M.04** FOUND | P2 | The settings file has few real settings: at least 13 | Add the missing settings
- **M.05** FOUND | P2 | The dialog has no search box, no per-setting reset, | Part of the row
- **M.06** FOUND | P2 | Terminal text size is a local variable (12 px, | Store in settings with
- **M.07** FOUND | P2 | Settings and the Control panel are two modals; | One entry point;
- **M.08** VERIFY | P2 | Only three write-style sidecar calls matched in | Trace each save path

## 2. Features to build or hide (61)

- **7.01** Office floor | A 2D office where each | NOT NEEDED | None. The idea of  
  _Status: DROPPED by plan: NOT NEEDED_
- **7.02** Real | Each agent is a real CLI | PARTIAL | Add a custom-command
- **7.03** Agent cards | Rows with status, engine, | PARTIAL | Fill ctx for every
- **7.04** Orchestrator | One lead agent you brief; | PARTIAL | Define the lead role,
- **7.05** Hire flow | Pick a CLI, model and | PARTIAL | Add role templates
- **7.06** Per-agent | Optional isolation so | NOT FOUND | Create a worktree per
- **7.07** Multiple | Open another vault with | PARTIAL | Window-per-vault using
- **7.08** Markdown | Each agent keeps markdown | PARTIAL | Add rules / notes
- **7.09** Semantic | Search shared memory by | NOT SET UP | Local embeddings
- **7.10** Hive | Agents write to an outbox; | PARTIAL | See section 9.
- **7.11** Single- | Only the harness commits | NOT FOUND | Introduce a commit
- **7.12** Knowledge | Your documents and | PARTIAL | Index docs and PDFs;
- **7.13** Kanban board | Tasks with dependencies, | PARTIAL | Board with columns,
- **7.14** Per-agent | A log of what each agent | PARTIAL | Live log with date
- **7.15** Automations | Scheduled missions with a | PARTIAL | Create, edit, run-now
- **7.16** Command | Live fleet monitoring, | PARTIAL | Fleet table plus CI
- **7.17** Skills | Shows what agents can | PARTIAL | Add catalogue search
- **7.18** Built-in IDE | A code editor with file | NOT FOUND | Embed a code editor
- **7.19** Human gates | Spend, scope and | PARTIAL | Gate list with approve
- **7.20** Autonomy | Controls how far each | PARTIAL | Map autonomy to real
- **7.21** Circuit | Escalates from steering to | NOT FOUND | Watch tokens, repeats
- **7.22** Budgets and | Per-agent token budgets, | PARTIAL | Per-agent view and
- **7.23** Temps | Short-lived agents for one | PARTIAL | Spawn from a card;
- **7.24** Clearing and | Compacts when context | VERIFY | Check and finish; show
- **7.25** Slack | One bot answers in chosen | PARTIAL | Connection settings
- **7.26** Webhooks | Inbound webhooks (GitHub, | PARTIAL | Create / test / delete
- **7.27** Local | A hotkey dictates into any | NOT SET UP | Bundle a small local
- **7.28** Own keys and | Per-provider API keys plus | PARTIAL | Endpoint list with a
- **7.29** Setup | First-run setup, a page | PARTIAL | Wizard with check
- **7.30** Languages | English, Simplified | VERIFY | Message catalogue,
- **7.31** Telemetry | Anonymous usage events | NOT FOUND | Optional; off by
- **7.32** Remote | Agents can be driven from | PARTIAL | Status indicator and a
- **7.33** Crash | A folder of crash reports | VERIFY | Write a record on
- **7.34** Live fleet | One JSON file with tokens, | NOT FOUND | Sidecar publishes it;
- **7.35** File-based | Spawn, clear and | NOT FOUND | Optional; only if
- **N.01** Recall bar | One search box (Ctrl+K) | NEW | Build the index in the
- **N.02** Graph lenses | Switch the same graph | NEW | Lens = a filter plus a
- **N.03** Live message | When an agent sends or | NEW | Respect reduced
- **N.04** Agent trail | At the end of a session | NEW | Template in the
- **N.05** Briefing | Pick blocks (role, rules, | NEW | Same builder produces
- **N.06** One-click | Ask an agent to write a | NEW | Handoff note format
- **N.07** Memory | Per agent: size against | NEW | Never overwrite
- **N.08** Link doctor | Shows broken links, | NEW | Repairs go through
- **N.09** Daily brief | Each morning the app | NEW | Off by default; one
- **N.10** Note to | Select text in a note to | NEW | Links appear as graph
- **N.11** Session | Scrub a past agent | NEW | Store sessions with
- **N.12** Approvals | A risky request shows the | NEW | Pairs with the shell
- **N.13** Spend ribbon | A small meter in the | NEW | Click opens the
- **N.14** Focus mode | Dim everything except the | NEW | Respects reduced
- **N.15** Split | Show two agent terminals, | NEW | Needs the single
- **N.16** Keyboard for | Every action is in the | NEW | One registry of
- **N.17** Quick | A global hotkey drops a | NEW | Tauri global shortcut;
- **N.18** Folder | Shows each working | NEW | Warn, never block;
- **N.19** Crash-safe | Unsent terminal input, | NEW | Write to one small
- **N.20** Doctor page | One page: sidecar up, | NEW | Lives in Settings >
- **N.21** Note history | Per-note history with a | NEW | Snapshots on save;
- **N.22** Playbooks | Named workflows (for | NEW | Stored as notes so
- **N.23** Pinned | Pin notes to an agent so | NEW | Show a warning past a
- **N.24** Quiet mode | One switch that mutes | NEW | Also the default on
- **N.25** Graph and | Export the graph as PNG or | NEW | Ships with the launch
- **N.26** Demo vault | A sample vault with a rich | NEW | Clearly labelled

## 3. Planned (187)

- **3.11** PLAN | - | Decide the brand direction for the pixel faces and | Keep pixel faces as
- **3.12** PLAN | - | Add a design-token documentation page inside the app | Generated from
- **3.13** PLAN | - | Add focus-visible rings, hover, pressed and disabled | Defined once in the
- **3.14** PLAN | - | Light-theme contrast check: extend | Fail the build under
- **3.15** PLAN | - | Window-size matrix test: screenshot every page at | Playwright or grim
- **4.15** PLAN | - | Introduce a 4-px spacing scale and a 12-column page | Audit every panel
- **4.16** PLAN | - | Pixel-diff screenshot test for the main screens so | Baseline images checked
- **5.13** PLAN | - | Primary / secondary / danger / ghost variants, three | Replace in all 46
- **5.14** PLAN | - | Keyboard map for all buttons and a command palette | Register actions once.
- **5.15** PLAN | - | Button audit test: every button has an accessible | Runs in the UI test
- **6.14** PLAN | - | Pixel brand font (Press Start 2P) is itself a | Decide with the owner.
- **6.15** PLAN | - | Automated check: a script fails the build on any | Runs in npm test.
- **6.16** PLAN | - | Browser-level check: load every screen and assert | Playwright run over
- **6.17** PLAN | - | Tabular numbers and a slightly larger line height so | font-variant-numeric:
- **6.18** PLAN | - | Window title, tray and native OS dialogs cannot be | Document in the README.
- **8.07** PLAN | - | Briefing template: Role, Objective, Rules, Tools and | Generated by the app,
- **8.08** PLAN | - | Tools and limits are computed from the real | Read the argv rules and
- **8.09** PLAN | - | Include the exact message JSON format and an example | Copy from the schema so
- **8.10** PLAN | - | Version stamp and hash in every briefing; the card | Changes are visible and
- **8.11** PLAN | - | Preview and edit the briefing in Add Agent and in | Live preview pane.
- **8.12** PLAN | - | Resend-briefing button and an automatic resend after | Keeps long sessions on
- **8.13** PLAN | - | Briefing lint: required sections present, size cap, | Fails before the agent
- **8.14** PLAN | - | Role templates (research, build, review, QA, writer) | Same as the hire-flow
- **8.15** PLAN | - | Handoff file per agent that is rewritten at clear | Matches the reference
- **8.16** PLAN | - | Integration test with a fake CLI per provider: the | Add to the Python suite.
- **9.07** PLAN | - | Thread view: messages grouped by work id with reply | Filter by agent, act,
- **9.08** PLAN | - | States: queued, delivered, read, done, failed; a | Visible in the UI.
- **9.09** PLAN | - | Rule: no acknowledgement-only or thank-you messages; | Cuts noise and token
- **9.10** PLAN | - | Loop guard: more than N messages between two agents | Pairs with the circuit
- **9.11** PLAN | - | Agents can write only to their own outbox; enforce | Test that a write
- **9.12** PLAN | - | Human compose box: message one or all agents, attach | Reuse it in the Inbox
- **9.13** PLAN | - | Size cap, retention and archive: old .done files | Keeps folders small.
- **9.14** PLAN | - | Search across all messages and export a thread. | Local index.
- **9.15** PLAN | - | Test suite: schema validation, ordering, duplicate | Part of the Python run.
- **10.07** PLAN | - | Give every agent Bash with the fenced deny list plus | Same list for all, so
- **10.08** PLAN | - | Run the agent CLI inside bwrap: read-only bind of | Even a shell that
- **10.09** PLAN | - | Block process tools against the app: kill, pkill and | Prevents closing
- **10.10** PLAN | - | Per-provider mapping: Codex sandbox set to | VERIFY each flag in the
- **10.11** PLAN | - | Shell command log per agent (command, time, exit) | Makes misuse visible.
- **10.12** PLAN | - | Integration test: an agent shell must fail to read, | Runs in CI before every
- **10.13** PLAN | - | Settings page shows the active policy in plain | No hidden rules.
- **11.07** PLAN | - | Typed request and response schemas for every sidecar | Frontend shows hint as
- **11.08** PLAN | - | Supervised sidecar: auto-restart with back-off, a | Directly answers 'keep
- **11.09** PLAN | - | Central logging: levels, rotating file, a Logs | Replaces raw console
- **11.10** PLAN | - | Time limits on every subprocess and sidecar call. | No call can hang the UI.
- **11.11** PLAN | - | Idempotent terminal start and stop; one lock per | No double CLI per agent.
- **11.12** PLAN | - | Secrets (API keys) in the OS keychain, not plain | Audit where keys are
- **11.13** PLAN | - | Dead-code and dependency audit: vulture for Python, | Remove what is unused.
- **11.14** PLAN | - | Data folder migrations with a version number and a | No silent data loss.
- **11.15** PLAN | - | Per-method tests for new code; keep all 288 tests | Gate commits on pytest.
- **11.16** PLAN | - | Capability endpoint: the backend reports what is set | Ends the 'Not set up'
- **12.03** PLAN | - | Motion tokens: durations 120 / 200 / 320 ms and | One place to tune feel.
- **12.04** PLAN | - | Dialogs fade and scale in; backdrops fade. | Svelte transitions.
- **12.05** PLAN | - | Tab content cross-fades; the active tab underline | Avoids hard cuts.
- **12.06** PLAN | - | Panels slide when opened; the right panel resize is | Respect reduced motion.
- **12.07** PLAN | - | Card hover lift, press-down, and a pulsing status | Makes live state
- **12.08** PLAN | - | Context bar and numbers tween to new values. | Counting animation.
- **12.09** PLAN | - | List items fade / slide in and out (notes, inbox, | keyed each blocks.
- **12.10** PLAN | - | Message envelope animation when an agent sends a | Shows the hive working.
- **12.11** PLAN | - | Graph: eased node movement, smooth zoom, highlight | Already animated; tune.
- **12.12** PLAN | - | Skeleton shimmer for loading lists (see section 13). | Same token durations.
- **12.13** PLAN | - | Terminal: smooth scroll and a soft flash on a new | Optional.
- **12.14** PLAN | - | Performance budget: animate transform and opacity | Keeps 60 fps on a weak
- **12.15** PLAN | - | Settings switch: Motion on / reduced / off, | User control.
- **13.03** PLAN | - | Waits that need a loader: graph build, vault sync, | One loader per wait with
- **13.04** PLAN | - | Components: top progress bar (indeterminate), | One Loading kit in
- **13.05** PLAN | - | A global rule: any sidecar call over 300 ms shows a | Consistent feel.
- **13.06** PLAN | - | Boot screen shows real steps (sidecar, vault, graph, | Use the existing
- **13.07** PLAN | - | Long jobs show a cancel button and elapsed time. | Memory index, skill
- **13.08** PLAN | - | Failures replace the loader with an error row and a | Never a silent spinner.
- **13.09** PLAN | - | Skeleton shapes for note list, inbox, task board, | Layout stays stable.
- **13.10** PLAN | - | Test: each loader has a minimum display time and an | aria-busy and live
- **14.02** PLAN | - | WHY 1: sync settings, agents and briefings across | Opt-in sync of non-
- **14.03** PLAN | - | WHY 2: one place to download releases, see the | Account page.
- **14.04** PLAN | - | WHY 3: unlock features that need a server: share | Account is the key to
- **14.05** PLAN | - | WHY 4: licence and plan (free, supporter) tied to a | Cleaner than keys.
- **14.06** PLAN | - | WHY 5: support and abuse control: rate limits, | Needed once there is a
- **14.07** PLAN | - | WHY 6: usage and budget history that follows the | Optional, off by
- **14.08** PLAN | - | Local-first rule: the app works fully offline with | Protects trust.
- **14.09** PLAN | - | Methods: GitHub and Google OAuth plus email link; no | Use a hosted auth
- **14.10** PLAN | - | Tokens stored in the OS keychain; sign-out wipes | Strongest privacy.
- **14.11** PLAN | - | Screens: Sign in, Sign up, Verify email, Account | Use the new Dialog
- **14.12** PLAN | - | Consent screen for telemetry and sync with plain | Off by default.
- **14.13** PLAN | - | Security review before launch: threat model, rate | Do not ship auth without
- **14.14** PLAN | - | Tests: sign-in happy path, expired token, offline, | Run against a staging
- **15.01** PLAN | - | Home: one-sentence promise, a short demo video or | Hero shows the real app,
- **15.02** PLAN | - | Download: per-OS installers, version, checksums, | Linked from the in-app
- **15.03** PLAN | - | Sign up and Sign in pages that match the app's auth | Email link plus GitHub
- **15.04** PLAN | - | Account dashboard: devices, plan, API keys for the | Minimal and clear.
- **15.05** PLAN | - | Docs: getting started, adding agents, briefings, | Built from markdown.
- **15.06** PLAN | - | Changelog and roadmap pages. | Generated from release
- **15.07** PLAN | - | Privacy policy, terms, security contact and a | Create SECURITY.md
- **15.08** PLAN | - | Status page link and a feedback form. | Optional.
- **15.09** PLAN | - | Tech: static site on Vercel with a hosted auth | Do not deploy until the
- **15.10** PLAN | - | Launch checklist: README refresh, demo GIF, tagged | Ties to 'push to GitHub
- **15.11** PLAN | - | Performance and accessibility targets: Lighthouse | Checked before launch.
- **15.12** PLAN | - | Analytics only with consent; no tracking before | Matches the app's
- **A.05** PLAN | - | Rule for the final build: every slice must pass | Stops regressions.
- **A.06** PLAN | - | Sidecar watchdog and a visible 'backend | No more silent failures.
- **A.07** PLAN | - | Feature flags for risky items (new terminal, | Settings page.
- **A.08** PLAN | - | Crash reports: write a local record of every UI | Includes version and  
  _Status: PARTLY: crash records written to crashes.jsonl (3540ccf)_
- **A.09** PLAN | - | A soak test: run the app for 8 hours with 3 agents | Catches leaks such as
- **A.10** PLAN | - | Disk and memory guard: warn when free disk or memory | Block heavy actions when  
  _Status: PARTLY: disk and memory warnings (3540ccf)_
- **B.03** PLAN | - | Pause every poll while the window is hidden or the | Saves battery and CPU.
- **B.04** PLAN | - | Virtualise long lists (notes, inbox, tasks). | Needed past about 500
- **B.05** PLAN | - | Lazy-load heavy panels (graph, monitor) and code- | Faster start.
- **B.06** PLAN | - | Measure start-up time and memory and store them per | Performance budget.
- **C.04** PLAN | - | End-to-end: launch the app, add an agent, send a | The test that would have
- **C.05** PLAN | - | Visual regression screenshots for the main screens. | See section 4.
- **C.06** PLAN | - | CI: run pytest, npm test, check, lint, build on | Add a workflow.
- **C.07** PLAN | - | Coverage report and a target for new code. | Informational at first.
- **E.04** PLAN | - | Keyboard path through every screen with a visible | Tab order test.
- **E.05** PLAN | - | Screen-reader labels for the terminal region and | Announce start, stop and
- **E.06** PLAN | - | Contrast test for both themes. | See section 3.
- **F.03** PLAN | - | Secrets in the OS keychain; never log keys. | Check logs for keys.
- **F.04** PLAN | - | SECURITY.md with a reporting address and a response | Create.
- **F.05** PLAN | - | Dependency scanning for npm, Python and Rust (cargo | CI step.
- **F.06** PLAN | - | Privacy page and an in-app list of everything that | Pairs with telemetry
- **G.03** PLAN | - | One installer per OS (AppImage, deb, msi, dmg) built | Attach to GitHub
- **G.04** PLAN | - | In-app update check and a changelog popup. | Complete it.
- **G.05** PLAN | - | First-run prerequisites page: tells which CLIs are | Make a full page.
- **G.06** PLAN | - | Clean-machine install test for each OS before each | Checklist in RELEASE.md.
- **H.02** PLAN | - | Extract all UI text into one catalogue. | Required for any
- **H.03** PLAN | - | Add right-to-left layout support from the start. | Mirrored spacing tokens.
- **H.04** PLAN | - | Plain-language error and empty-state copy review. | One tone for the app.
- **I.03** PLAN | - | ARCHITECTURE.md: sidecar, terminals, vault, graph, | Helps the next builder.
- **I.04** PLAN | - | DESIGN.md generated from tokens.css. | See section 3.
- **I.05** PLAN | - | RELEASE-CHECKLIST.md: tests, screenshots, install | Used for every release.
- **J.04** PLAN | - | Search-to-focus, saved views and an export to image. | Graph is a launch demo
- **J.05** PLAN | - | Memory page: rules, notes and a size meter per | Matches the reference
- **K.11** PLAN | - | One connector registry in the backend (new | Unit test: every
- **K.12** PLAN | - | Card states in plain words: Not connected, | Same chip style as the
- **K.13** PLAN | - | Slack connector: enable switch, mode (socket, | Tokens only in the OS
- **K.14** PLAN | - | Webhook connector: add, edit, remove and rotate- | Every inbound call lands
- **K.15** PLAN | - | Scheduled missions (Automations): label, message | Unify with the existing
- **K.16** PLAN | - | Default responders: who answers Slack, and who takes | Two dropdowns in the
- **K.17** PLAN | - | MCP servers: read the user-level and project-level | Read-only first, then
- **K.18** PLAN | - | GitHub connector: gh login status, a repository per | Uses the user's own gh
- **K.19** PLAN | - | Notion, Google Calendar, Gmail and Google Drive as | Do not claim any of them
- **K.20** PLAN | - | Local model card: Ollama host, reachable yes or no, | Also fixes the
- **K.21** PLAN | - | A connector that cannot run yet is still a real | This is the 'working
- **K.22** PLAN | - | Secrets rule: a setup request file is deleted after | Test: grep the logs
- **K.23** PLAN | - | Connection log: every connect, test, disconnect and | Reuse the Activity log
- **K.24** PLAN | - | Failure handling: back off after repeated errors, | Pairs with section A
- **K.25** PLAN | - | Per-agent connector permissions: which agent may use | Default deny for new
- **K.26** PLAN | - | Test kit: one fake server per connector kind (Slack, | Runs in CI.
- **L.11** PLAN | - | Shared Tab component: items, selected value, | Replaces 3 hand-made tab
- **L.12** PLAN | - | Placeholder contract: a tab or panel whose backend | Every 'Not set up' text
- **L.13** PLAN | - | Loading and error states for every tab: skeleton | See section 13.
- **L.14** PLAN | - | Remember the last open tab per window in settings; | Small setting row in
- **L.15** PLAN | - | Tab 'terminal': live terminal and message box. Works | Section 1 and section A
- **L.16** PLAN | - | Tab 'monitor': agents, folders and GitHub issues. | Uses the GitHub
- **L.17** PLAN | - | Tab 'tasks': cards in four columns (todo, doing, | Matches the reference
- **L.18** PLAN | - | Tab 'inbox': threads, unread count, filter by agent | One schema with section
- **L.19** PLAN | - | Tab 'ask me': questions to the human with a short | Never lets a question
- **L.20** PLAN | - | Tab 'triggers': network mode, scheduled jobs and | Uses section K forms.
- **L.21** PLAN | - | Tab 'history': past sessions with search, open and | Chat history calls
- **L.22** PLAN | - | Tab 'memory': notes per agent with a size meter | Shows when memory is
- **L.23** PLAN | - | Tab 'activity': the tool log with filters by agent, | Same row style as the
- **L.24** PLAN | - | Tab 'skills': installed skills with enable per | Remove needs a confirm
- **L.25** PLAN | - | Tab 'temps': the short-lived helper agents the | VERIFY first that
- **L.26** PLAN | - | Agent panel tabs (terminal, git, messages, traces): | One handler path for all
- **L.27** PLAN | - | Tab switch animation: a short cross-fade and a | Section 12.
- **L.28** PLAN | - | Screenshot matrix for tabs: every tab, empty, | Section C testing.
- **M.09** PLAN | - | Layout: a left rail of categories in groups, a right | Replaces both dialogs'
- **M.10** PLAN | - | Setting row component: label, one line of help, the | One component, used for
- **M.11** PLAN | - | General: language, theme (dark, light, system), UI | Theme work is section 3.
- **M.12** PLAN | - | Appearance: accent colour, density (compact or | Section 6 and section
- **M.13** PLAN | - | Agents: default provider and model, default | Section 8 and section
- **M.14** PLAN | - | Terminal: font size, scrollback lines, cursor style, | Applies to Hippo and
- **M.15** PLAN | - | Inbox and messages: delivery interval, how long to | Section 9.
- **M.16** PLAN | - | Budgets and limits: token caps for the app and the | Moves out of the Control
- **M.17** PLAN | - | Models and keys: the 14 provider keys (last four | Separate from
- **M.18** PLAN | - | Connectors: the cards from section K, in one page. | Replaces 'Integrations'.
- **M.19** PLAN | - | Memory and knowledge: memory size cap, condense | Section B polling.
- **M.20** PLAN | - | Notifications: desktop alerts for an 'ask me' | Off by default until
- **M.21** PLAN | - | Privacy and data: telemetry on or off (off by | Section F.
- **M.22** PLAN | - | Account: sign in, sign out, plan, devices. Hidden | Section 14.
- **M.23** PLAN | - | Keyboard shortcuts: a table of every shortcut, | Section E.
- **M.24** PLAN | - | Advanced: logs viewer, feature flags, diagnostics | Replaces the
- **M.25** PLAN | - | About: version, licence, update check, links to docs | Section I.
- **M.26** PLAN | - | Control panel becomes Operations: tabs for Overview | No setting appears
- **M.27** PLAN | - | One settings schema in the backend: key, type, | A mechanical test checks
- **M.28** PLAN | - | Safe writes: write to a temporary file and rename it | Corrupt file falls back
- **M.29** PLAN | - | Export and import settings without secrets. | Helps moving to a new
- **M.30** PLAN | - | Command palette entries 'Settings: <name>' jump to | Search and palette share
- **M.31** PLAN | - | Settings tests: schema round-trip, default fill, | Part of the 288-test

## 4. Decisions and work items (10)

- **D.01** Build | No app code was built from this plan. | Fable 5.2 builds in the
- **D.02** Terminal garble | The agent side-panel terminal (wdwdw) is | Needs a CLI restart for a  
  _Status: LIKELY FIXED: same as 1.01_
- **D.03** WhatsApp promise | 'Its completed sir.' plus a screenshot of | Send only after the  
  _Status: OPEN: needs the sidebar screenshot check first_
- **D.04** Failing JS test | 'UI source has no hardcoded colors' fails: | Move colours to tokens,  
  _Status: CLOSED: npm test passes (colour check)_
- **D.05** ESLint | 4 errors: unused ARC_ROW and SHAPE_LONG, one | Fix; lint must be zero  
  _Status: CLOSED: ESLint 0 errors_
- **D.06** GitHub push and | Not done. The target (main or hippo-audit- | You decide; no force-push.  
  _Status: DECIDED: target hippo-audit-fixes pushed to origin (dbd55ed); main untouched_
- **D.07** Features to build | Your decision is pending on which 'Not set | Until decided, each becomes  
  _Status: DECIDED: "all that fits our app"; list of what fits still to write_
- **D.08** Fonts | The monospace token change and the bundled | Section 6.
- **D.09** Security and | The shell sandbox, briefing builder, one | Sections 8, 9, 10, 14, 15
- **D.10** Open requests | The scheduler's 'obsidian' update request | Needs your answer before  
  _Status: OPEN: needs your answer (obsidian request, mr, hanis)_

## 5. Confirmed, no action (7)

- **2.02** FOUND | - | Python tests pass: 288 passed, 1 deselected in 16.73 | Keep as the safety net;
- **2.03** FOUND | - | The dev run logged no error, warning or traceback | None; confirms the
- **10.06** FOUND | - | bwrap is available; firejail is not. | Use bwrap to wrap the
- **14.01** FOUND | - | No sign-in or sign-up exists: AccountDialog is | Keep it for local setup;
- **C.01** FOUND | - | Python: 288 passed, 1 deselected. | Keep.
- **C.10** FOUND | - | svelte-check reports 0 errors and 0 warnings. | Keep it in CI.
- **J.01** FOUND | - | Three renderers exist: canvas, ASCII and | Keep; share one label

## 6. Already fixed in the plan (6)

- **1.16** FIXED | - | Tab switch used to stop the agent CLI. | None.
- **1.17** FIXED | - | Model field was not passed to the CLI. | None.
- **1.18** FIXED | - | Agent folder was not used as the working directory. | None.
- **1.19** FIXED | - | AgentPanel buttons IDE, stop, block tools, | None.
- **1.20** FIXED | - | Duplicate card_list / card_create / card_update | None.
- **1.21** FIXED | - | chat() cleared the pause before validating | None.
