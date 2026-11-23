// Only the part of Playwright's Page this file uses, so the app can import it without Playwright.
type Page = {
  addInitScript<A>(fn: (arg: A) => void, arg: A): Promise<unknown> | unknown;
};

// Stands in for the Tauri bridge and the Python sidecar. It answers the same requests with the
// same shapes as core/__main__.py, so the UI runs unchanged. The Python side has its own tests.
// `orphan` adds a fourth note with no links, for the orphans toggle. `noVault` starts with no brain
// open, so the setup opens, until "open" is called. `signedIn` starts with a saved Claude key.
export async function mockSidecar(
  page: Page,
  options: {
    orphan?: boolean;
    noVault?: boolean;
    signedIn?: boolean;
    /** This build has the Hippocampus sign-in service set up (Settings > Account shows). */
    account?: boolean;
    intro?: boolean;
    /** Act out the very first start: the setup checklist opens by itself. */
    firstRun?: boolean;
    /** Methods that fail, to test what the user is told. */
    fail?: string[];
  } = {},
): Promise<void> {
  await page.addInitScript(
    (opts: {
      orphan: boolean;
      noVault: boolean;
      signedIn: boolean;
      account: boolean;
      intro: boolean;
      firstRun: boolean;
      fail: string[];
    }) => {
      // Tests start past the first-run setup checklist unless they ask for it.
      try {
        if (!opts.firstRun) localStorage.setItem("hippocampus.setupSeen", "1");
      } catch {
        /* storage blocked */
      }
      // Tests skip the start-up logo (Settings > Appearance), which otherwise covers the app for 12 seconds.
      try {
        const saved = JSON.parse(
          localStorage.getItem("hippocampus.prefs") ?? "{}",
        );
        if (!opts.intro && saved.intro === undefined)
          localStorage.setItem(
            "hippocampus.prefs",
            JSON.stringify({ ...saved, intro: "off" }),
          );
      } catch {
        /* storage blocked: the logo shows, the test is only slower */
      }
      const callbacks = new Map<number, (payload: unknown) => void>();
      const listeners = new Map<string, number[]>();
      let nextId = 1;
      const pending = new Map<number, (value: unknown) => void>();

      const graph = {
        nodes: [
          { id: "alpha.md", title: "Alpha", tags: ["idea"] },
          { id: "beta.md", title: "Beta", tags: [] },
          { id: "gamma.md", title: "Gamma", tags: ["idea"] },
        ],
        edges: [
          ["alpha.md", "beta.md"],
          ["beta.md", "gamma.md"],
        ],
      };
      if (opts.orphan)
        graph.nodes.push({ id: "delta.md", title: "Delta", tags: [] });
      let vaultOpen = !opts.noVault;
      // The Hippocampus account. Tests call window.__finishSignIn() to act out the browser coming back.
      let userShares = [
        {
          id: "s1",
          title: "Plan for Q4",
          expires_at: "2099-01-01T00:00:00Z",
          url: "https://site.test/share.html#s1",
        },
      ];
      const userAccount = {
        configured: opts.account,
        signed_in: false,
        waiting: false,
        consent: { sync: false, usage: false, asked: false },
        email: "",
        name: "",
        plan: "free",
      };
      (window as unknown as { __finishSignIn: () => void }).__finishSignIn =
        () => {
          Object.assign(userAccount, {
            signed_in: true,
            waiting: false,
            email: "ada@example.com",
            name: "Ada",
          });
        };
      // Every terminal start and stop, in order, for tests to read.
      // Tests set window.__boot to act out a backend restart.
      const bootId = () =>
        (window as unknown as { __boot?: string }).__boot ?? "boot-1";
      let shellOn = false;
      const NUMBER_LIMITS: Record<string, [number, number]> = {
        "ai.max_tool_calls": [1, 200],
        "memory.max_bytes": [1000, 1000000],
        "inbox.delivery_seconds": [1, 60],
      };
      const numbers: Record<string, number> = {
        "ai.max_tool_calls": 20,
        "memory.max_bytes": 32000,
        "inbox.delivery_seconds": 3,
      };
      const shellState = () => ({
        on: shellOn,
        sandbox_available: true,
        main: ["Shell: allowed for simple tasks."],
        agents: shellOn
          ? [
              "Shell: allowed for simple tasks.",
              "Your program runs in a sandbox.",
            ]
          : ["Shell: not available to this agent."],
        note: "Applies to agents on Claude Code.",
      });
      // Messages between agents, in the backend's schema; a sent message is added at the top.
      const inboxRows: Record<string, string>[] = [
        {
          id: "m-1",
          from: "hippoherman",
          to: "kevin",
          act: "request",
          subject: "Research the plan",
          body: "Read the audit and list the gaps.",
          work: "T-1",
          thread: "m-1",
          priority: "normal",
          created_at: "2026-10-29T12:30:00+00:00",
          state: "queued",
        },
        {
          id: "m-2",
          from: "kevin",
          to: "hippoherman",
          act: "done",
          subject: "Research done",
          body: "Three gaps found.",
          work: "T-1",
          thread: "m-1",
          priority: "normal",
          created_at: "2026-10-29T13:10:00+00:00",
          state: "delivered",
        },
        {
          id: "m-3",
          from: "kevin",
          to: "zed",
          act: "request",
          subject: "Lost message",
          body: "x",
          work: "",
          thread: "m-3",
          priority: "normal",
          created_at: "2026-10-28T09:00:00+00:00",
          state: "failed",
          failed: 'No agent has the id "zed".',
        },
      ];
      const terminalCalls: Record<string, unknown>[] = [];
      (window as unknown as { __terminalCalls: unknown }).__terminalCalls =
        terminalCalls;
      let savedAgents: unknown[] = [];
      // The Claude key is kept here, never sent back to the page: account reports only yes or no.
      let claudeKey: string | null = opts.signedIn ? "sk-saved" : null;
      const workspaceFolders = ["IT"];
      let crashRows: { at: string; source: string; message: string }[] = [];

      // The note text the drawer reads through the "read" method.
      const noteHistory: Record<string, { id: string; text: string }[]> = {};
      const texts: Record<string, string> = {
        "alpha.md": [
          "# Alpha",
          "",
          "A first idea, see [[Beta]] and [[gamma|the last note]].",
          "",
          "## Steps",
          "",
          "- read the [docs](https://example.com)",
          "- check `config/settings.toml`",
          "",
          "```",
          "let x = 1;",
          "```",
          "",
        ].join("\n"),
        "beta.md": "# Beta\n",
        "gamma.md": "# Gamma\n\nNo links here.\n",
      };

      const emit = (name: string, payload: unknown) => {
        for (const id of listeners.get(name) ?? [])
          callbacks.get(id)?.({ event: name, payload, id });
      };

      // Tests call this to act out an event pushed by the backend.
      (
        window as unknown as { __sidecarEvent?: (payload: unknown) => void }
      ).__sidecarEvent = (payload) => emit("sidecar-event", payload);

      const diff =
        "--- /dev/null\n+++ b/ideas/new.md\n@@ -0,0 +1 @@\n+# New idea\n";

      async function chat(args: {
        params: { chat: number; text: string; continue?: boolean };
      }): Promise<unknown> {
        const { chat, text } = args.params;
        if (args.params.continue)
          return { reply: "Carried on to the end.", stopped: false };
        if (text.includes("many"))
          return { reply: "", stopped: false, limit: 20 };
        if (text.includes("long")) {
          // Runs until the user presses Stop.
          return new Promise((resolve) =>
            pending.set(chat, () => resolve({ reply: "", stopped: true })),
          );
        }
        if (text.includes("make")) {
          emit("sidecar-event", {
            event: "confirm",
            chat,
            call: "c1",
            name: "create_note",
            tier: "write",
            preview: diff,
          });
          return new Promise((resolve) =>
            pending.set(chat, (approved) =>
              resolve({
                reply: approved
                  ? "Created ideas/new.md."
                  : "Okay, I did not create it.",
                stopped: false,
              }),
            ),
          );
        }
        emit("sidecar-event", {
          event: "tool",
          chat,
          call: "t1",
          name: "search_notes",
          tier: "read",
          status: "running",
        });
        emit("sidecar-event", {
          event: "tool",
          chat,
          call: "t1",
          name: "search_notes",
          tier: "read",
          status: "done",
        });
        return { reply: "Found Alpha in projects/alpha.md.", stopped: false };
      }

      // The assistant tool allowlist the fake sidecar holds: null means every tool.
      let allowlist: string[] | null = null;

      // Control panel state the fake sidecar holds.
      let networkMode = "off";
      let budgetCaps = {
        app: { five_hour: 0, daily: 200000, weekly: 0, monthly: 0 },
        assistant: { five_hour: 20000, daily: 50000, weekly: 0, monthly: 0 },
      };
      const budgetUsed = {
        app: { five_hour: 4100, daily: 12400, weekly: 30100, monthly: 41000 },
        assistant: {
          five_hour: 3900,
          daily: 9800,
          weekly: 25000,
          monthly: 33000,
        },
      };
      let allowance = false;
      const activityRows = [
        {
          ts: "2026-10-27T09:12:04+00:00",
          kind: "approval",
          tool: "create_note",
          tier: "write",
          approved: true,
        },
        {
          ts: "2026-10-27T09:12:01+00:00",
          kind: "tool",
          tool: "search_notes",
          tier: "read",
          status: "done",
        },
        {
          ts: "2026-10-27T09:10:48+00:00",
          kind: "budget",
          text: "paused: assistant daily cap reached",
        },
        {
          ts: "2026-10-27T08:55:10+00:00",
          kind: "error",
          method: "chat",
          text: "network is Off: no call to api.anthropic.com",
        },
        {
          ts: "2026-10-27T08:50:00+00:00",
          kind: "setting",
          text: "network set to converse",
        },
      ];
      const hookRows: { id: string; name: string; kind: string }[] = [];
      const connectorRows = [
        {
          id: "ollama",
          kind: "check",
          name: "Local model (Ollama)",
          what: "Runs a model on this computer, with no key and no network.",
          state: "Connected",
          reason:
            "Answered at http://127.0.0.1:11434. Model in use: qwen2.5:1.5b.",
          needs: "",
          details: ["qwen2.5:1.5b", "llama3.2:3b"],
          checked: "2026-11-13T20:00:00+00:00",
        },
        {
          id: "github",
          kind: "check",
          name: "GitHub",
          what: "Open issues for an agent's folder, shown on the Monitor tab.",
          state: "Not connected",
          reason: "You are not logged in. Run `gh auth login`.",
          needs: "gh login",
          details: [],
          checked: "2026-11-13T20:00:00+00:00",
        },
        {
          id: "slack",
          kind: "card",
          name: "Slack",
          what: "One bot that answers in chosen channels and replies in threads.",
          state: "Needs setup",
          reason: "No Slack calls are built yet.",
          needs: "A token store and a message bridge in the backend",
          details: [],
          checked: "2026-11-13T20:00:00+00:00",
        },
      ];
      const jobRows = [
        {
          id: "link-check",
          name: "Weekly link check",
          kind: "link_check",
          every_days: 7,
          enabled: true,
          last_run: "2026-10-26T07:00:00+00:00",
        },
      ];
      let missionRows: {
        id: string;
        label: string;
        message: string;
        agent: string;
        every_minutes: number | null;
        days: number[];
        at: string;
        enabled: boolean;
        last_run: string | null;
      }[] = [];
      let helperRows: {
        id: number;
        prompt: string;
        status: string;
        result: string;
      }[] = [
        {
          id: 1,
          prompt: "Summarise the project notes",
          status: "done",
          result: "Three notes cover the roadmap.",
        },
      ];
      let skillRows = [
        {
          name: "tidy-notes",
          description: "Keeps the note list tidy",
          path: "skills/tidy-notes",
        },
      ];
      const keyRows = () => [
        {
          provider: "claude",
          label: "Claude (Anthropic)",
          saved: claudeKey !== null,
          hint: claudeKey ? claudeKey.slice(-4) : null,
        },
        { provider: "openai", label: "OpenAI", saved: false, hint: null },
      ];

      async function sidecarCall(args: {
        method: string;
        params?: Record<string, unknown>;
      }): Promise<unknown> {
        if (opts.fail.includes(args.method))
          throw new Error(`mock: ${args.method} is set to fail`);
        switch (args.method) {
          case "agents":
            return { agents: savedAgents };
          case "save_agents":
            savedAgents = (args.params?.agents as unknown[]) ?? [];
            return { agents: savedAgents };
          case "graph":
            if (!vaultOpen) throw new Error("no vault is open");
            return graph;
          case "open":
            if (!String(args.params?.vault).startsWith("/"))
              throw new Error("vault folder not found");
            vaultOpen = true;
            return { vault: args.params?.vault };
          case "tasks":
            return {
              tasks: [
                {
                  id: "MDF-1",
                  title: "Ship the Tasks page",
                  status: "doing",
                  assignee: "hippoherman",
                  updatedAt: null,
                },
                {
                  id: "MDF-2",
                  title: "Check the Inbox feed",
                  status: "todo",
                  assignee: null,
                  updatedAt: null,
                },
                {
                  id: "MDF-3",
                  title: "Pick the release date",
                  status: "blocked",
                  assignee: "kevin",
                  updatedAt: null,
                  waiting: true,
                },
              ],
            };
          case "inbox":
            return {
              messages: inboxRows,
              acts: [
                "request",
                "inform",
                "note",
                "propose",
                "query",
                "agree",
                "refuse",
                "done",
              ],
            };
          case "inbox_search": {
            const words = String(args.params?.query ?? "").toLowerCase();
            return {
              messages: inboxRows.filter((m) =>
                `${m.subject} ${m.body} ${m.from} ${m.to}`
                  .toLowerCase()
                  .includes(words),
              ),
            };
          }
          case "inbox_thread":
            return {
              messages: inboxRows.filter(
                (m) => m.thread === args.params?.thread,
              ),
              markdown: "# Research the plan\n",
            };
          case "task_send": {
            const targets =
              args.params?.to === "all"
                ? ["hippoherman"]
                : [String(args.params?.to)];
            const ids = targets.map((to, i) => {
              const id = `m-new-${inboxRows.length + i}`;
              inboxRows.unshift({
                id,
                from: "user",
                to,
                act: "request",
                subject: String(args.params?.subject ?? ""),
                body: String(args.params?.body ?? ""),
                work: "",
                thread: id,
                priority: String(args.params?.priority ?? "normal"),
                created_at: "2026-11-12T08:00:00+00:00",
                state: "queued",
              });
              return id;
            });
            return { id: ids[0], ids };
          }
          case "settings":
            return {
              general: { vault: "data/brains/Hippocampus", network: "off" },
              agents: {
                provider: "claude",
                model: "claude-sonnet-5-5",
                ollama: "qwen2.5:1.5b",
              },
              budgets: {
                app: { five_hour: 0, daily: 0, weekly: 0, monthly: 0 },
                assistant: {
                  five_hour: 0,
                  daily: 50000,
                  weekly: 0,
                  monthly: 0,
                },
                max_tool_calls: numbers["ai.max_tool_calls"],
              },
              memory: { max_bytes: numbers["memory.max_bytes"] },
              inbox: { delivery_seconds: numbers["inbox.delivery_seconds"] },
              limits: NUMBER_LIMITS,
              shell: shellState(),
            };
          case "set_number": {
            const key = String(args.params?.key);
            const value = Number(args.params?.value);
            const limits = NUMBER_LIMITS[key];
            if (!limits || !(value >= limits[0] && value <= limits[1]))
              throw new Error(
                `${key} must be a whole number from ${limits?.[0]} to ${limits?.[1]}`,
              );
            numbers[key] = value;
            return { key, value };
          }
          case "set_agent_shell":
            shellOn = Boolean(args.params?.on);
            return shellState();
          case "memory":
            return {
              notes: [
                {
                  agent: "god",
                  bytes: 4096,
                  updated_at: "2026-10-29T13:30",
                  rules: 4,
                  notes: 12,
                  repeated: 2,
                },
                { agent: "kevin", bytes: 2048, updated_at: "2026-10-28T09:12" },
                {
                  agent: "oscar",
                  bytes: 30000,
                  updated_at: "2026-10-27T08:00",
                },
              ],
              max_bytes: 32000,
            };
          case "user_account":
            return structuredClone(userAccount);
          case "user_sign_in":
            if (!userAccount.configured)
              throw new Error("Accounts are not set up in this build yet.");
            userAccount.waiting = true;
            return { url: "https://auth.test/auth/v1/authorize" };
          case "user_sign_in_cancel":
            userAccount.waiting = false;
            return structuredClone(userAccount);
          case "user_sign_out":
          case "user_delete":
            Object.assign(userAccount, {
              signed_in: false,
              email: "",
              name: "",
            });
            return structuredClone(userAccount);
          case "user_sync_save":
            return { saved: ["agents", "settings"], usage_days: 0 };
          case "user_sync_fetch":
            return {
              fetched: ["agents", "settings"],
              saved_at: "2026-11-18T00:00:00Z",
            };
          case "user_shares":
            return { shares: structuredClone(userShares) };
          case "user_share_delete":
            userShares = userShares.filter((x) => x.id !== args.params?.id);
            return { shares: structuredClone(userShares) };
          case "share":
            return {
              url: "https://site.test/share.html#new",
              expires_at: "2026-11-18T01:00:00Z",
            };
          case "user_consent":
            userAccount.consent = {
              sync: args.params?.sync === true,
              usage: args.params?.usage === true,
              asked: true,
            };
            return structuredClone(userAccount);
          case "account":
            return {
              claude: claudeKey !== null,
              model: claudeKey !== null ? "claude-sonnet-5-5" : "qwen2.5:1.5b",
              provider: claudeKey !== null ? "claude" : "ollama",
              ready: claudeKey !== null,
              // A test sets window.__noOllama to act out no key and no Ollama.
              local:
                claudeKey !== null ||
                !(window as unknown as { __noOllama?: boolean }).__noOllama,
            };
          case "read": {
            const path = String(args.params?.path);
            if (!(path in texts)) throw new Error(`mock: no note ${path}`);
            return { id: path, text: texts[path] };
          }
          // The graph's right-click actions, as core/__main__.py answers them.
          case "note_text":
            return {
              id: args.params?.path,
              text: texts[String(args.params?.path)],
            };
          case "note_save": {
            const at = String(args.params?.path);
            const kept = (noteHistory[at] ??= []);
            kept.unshift({
              id: String(1_800_000_000_000 + kept.length),
              text: texts[at] ?? "",
            });
            texts[at] = String(args.params?.text);
            return { saved: `edited ${at}` };
          }
          case "search_all": {
            const q = String(args.params?.query ?? "").toLowerCase();
            return {
              notes: Object.keys(texts)
                .filter((path) =>
                  (path + texts[path]).toLowerCase().includes(q),
                )
                .map((path) => ({
                  path,
                  title: path.replace(/\.md$/, ""),
                  snippet: "",
                })),
              messages: "release".includes(q)
                ? [
                    {
                      id: "m9",
                      from: "pam",
                      to: "user",
                      subject: "Release notes",
                      snippet: "",
                    },
                  ]
                : [],
              tasks: [],
              events: [],
              agents: "hippoherman".includes(q)
                ? [{ id: "hippoherman", name: "Hippoherman" }]
                : [],
            };
          }
          case "handoff":
            return {
              note: `Handoffs/2026-11-23 1400 ${String(args.params?.from)} to Hippoherman.md`,
              message: "m1",
            };
          case "breakers":
            return {
              breakers:
                (window as unknown as { __breakers?: unknown[] }).__breakers ??
                [],
            };
          case "fleet":
            return {
              path: "/home/me/.hippocampus/office/fleet.json",
              agents: [{ id: "hippoherman", status: "idle" }],
            };
          // Note history, as core/session_notes.py answers it.
          case "note_history":
            return {
              id: args.params?.path,
              versions: (noteHistory[String(args.params?.path)] ?? []).map(
                (v) => ({
                  id: v.id,
                  time: Number(v.id),
                  chars: v.text.length,
                  first: v.text.split("\n").find((l) => l.trim()) ?? "",
                }),
              ),
            };
          case "note_version":
          case "note_restore": {
            const at = String(args.params?.path);
            const kept = (noteHistory[at] ?? []).find(
              (v) => v.id === args.params?.version,
            );
            if (!kept) throw new Error("That version is no longer kept.");
            if (args.method === "note_restore") {
              const list = (noteHistory[at] ??= []);
              list.unshift({
                id: String(1_800_000_000_000 + list.length),
                text: texts[at] ?? "",
              });
              texts[at] = kept.text;
            }
            return { id: at, version: kept.id, text: kept.text };
          }
          case "note_colour":
            return { changed: [args.params?.path] };
          case "note_delete":
            return { deleted: [args.params?.path] };
          case "chat":
            return chat(
              args as unknown as { params: { chat: number; text: string } },
            );
          case "confirm": {
            const params = args.params as { call: string; approve: boolean };
            const w = window as unknown as {
              __approvals?: { call: string }[];
              __decided?: [string, boolean][];
            };
            w.__approvals = (w.__approvals ?? []).filter(
              (a) => a.call !== params.call,
            );
            (w.__decided ??= []).push([params.call, params.approve]);
            // The fake sidecar keeps one pending chat per card: find it through the call id.
            for (const [chat, resolve] of pending) {
              resolve(params.approve);
              pending.delete(chat);
              emit("sidecar-event", {
                event: "tool",
                chat,
                call: params.call,
                name: "create_note",
                tier: "write",
                status: params.approve ? "done" : "declined",
              });
            }
            return { call: params.call };
          }
          case "tools": {
            const rows = [
              { name: "read_note", tier: "read" },
              { name: "create_note", tier: "write" },
            ];
            return {
              tools: rows.map((t) => ({
                ...t,
                allowed: allowlist === null || allowlist.includes(t.name),
              })),
              every: allowlist === null,
            };
          }
          case "set_tools":
            allowlist = (args.params?.names ?? null) as string[] | null;
            return { names: allowlist };
          case "stop":
            for (const [chat, resolve] of pending) {
              resolve(undefined);
              pending.delete(chat);
            }
            return { stopped: true };
          // The control panel: the same shapes as core/__main__.py answers.
          case "network":
            return {
              mode: networkMode,
              modes: ["off", "listen", "converse", "open"],
            };
          case "set_network":
            networkMode = String(args.params?.mode);
            return {
              mode: networkMode,
              modes: ["off", "listen", "converse", "open"],
            };
          case "budget":
            return {
              caps: budgetCaps,
              used: budgetUsed,
              allowance,
              by_agent: { assistant: 12000, kevin: 3400 },
            };
          case "set_budget":
            budgetCaps = args.params as typeof budgetCaps;
            return { caps: budgetCaps, used: budgetUsed, allowance };
          case "budget_allow":
            allowance = true;
            return { allowance: true };
          case "save_export":
            return {
              path: `/home/me/.hippocampus/exports/20261114-${String(args.params?.name)}`,
            };
          case "export_notes":
            return {
              path: "/home/me/.hippocampus/exports/20261114-notes.zip",
              notes: 3,
            };
          case "clear_activity":
            return { rows: [] };
          case "activity":
            // A test sets window.__newActivity to act out a line written after the tab was read.
            return {
              rows: (window as unknown as { __newActivity?: boolean })
                .__newActivity
                ? [
                    {
                      ts: "2026-10-27T10:00:00+00:00",
                      kind: "setting",
                      text: "pushed by an event",
                    },
                    ...activityRows,
                  ]
                : activityRows,
            };
          case "asks":
            return {
              asks: [
                {
                  call: "ask-1",
                  question: "Which folder should the new note go in?",
                },
              ],
              // Tests put waiting tool approvals here; confirm removes them.
              approvals:
                (
                  window as unknown as {
                    __approvals?: {
                      call: string;
                      name: string;
                      preview: string;
                    }[];
                  }
                ).__approvals ?? [],
            };
          case "answer":
            return { call: args.params?.call };
          case "memory_status":
            return {
              ready: false,
              reason:
                "No embedding model is installed, so search by meaning is not set up. Text search still works.",
              max_bytes: 32000,
            };
          case "memory_search":
            if (args.params?.mode === "meaning")
              throw new Error("Not set up: no embedding model is installed.");
            return { mode: "text", hits: ["ideas/memory.md"] };
          case "system":
            return { cpu: 42, ram: 61, swap: 12, disk: 33, disk_free: 120.5 };
          case "watchers":
            return {
              watchers: [
                {
                  name: "brain",
                  kind: "vault watcher",
                  status: "stopped",
                  last_event: null,
                },
                {
                  name: "Weekly link check",
                  kind: "trigger",
                  status: "stopped",
                  last_event: null,
                },
              ],
            };
          case "chat_history":
            return { sessions: [] };
          case "current_session":
            return { session: "mock-session" };
          case "chat_history_save":
            return { saved: true };
          case "agent_session":
          case "new_session":
            return { session: "mock-session" };
          case "provider_status":
            return { clis: [] };
          case "local_status":
            return {
              servers: [
                { provider: "ollama", running: true },
                { provider: "lmstudio", running: false },
                { provider: "vllm", running: false },
              ],
            };
          case "set_vault":
            if (!String(args.params?.vault).startsWith("/"))
              throw new Error("vault folder not found");
            vaultOpen = true;
            return { vault: args.params?.vault, notes: 3 };
          case "remove_data":
            return { removed: true };
          case "record_crash":
            crashRows.unshift({
              at: String(args.params?.at),
              source: String(args.params?.source),
              message: String(args.params?.message),
            });
            return { ok: true };
          case "crashes":
            return { crashes: crashRows };
          case "clear_crashes":
            crashRows = [];
            return { crashes: [] };
          case "workspaces":
            return { root: "/home/me/workspaces", folders: workspaceFolders };
          case "create_workspace":
            workspaceFolders.push(String(args.params?.name));
            return {
              root: "/home/me/workspaces",
              folders: [...workspaceFolders],
            };
          case "terminal_start":
            terminalCalls.push({ method: args.method, ...args.params });
            return { running: true };
          case "terminal_stop":
            terminalCalls.push({ method: args.method, ...args.params });
            return { ok: true };
          case "logs":
            return {
              path: "/home/me/.hippocampus/logs/backend.log",
              lines: [
                "2026-11-12 10:00:00 INFO hippocampus.core: Synced vault",
                "2026-11-12 10:00:05 WARNING hippocampus.core: slow call",
              ],
            };
          case "terminal_input": {
            // A test reads window.__typed to see what was typed into a terminal.
            const w = window as unknown as { __typed?: string[] };
            (w.__typed ??= []).push(String(args.params?.data));
            return { ok: true };
          }
          case "terminal_resize":
            return { ok: true };
          case "terminal_context":
            return { percent: 42 };
          case "provider_usage": {
            const days = (values: number[]) => [
              ...Array.from({ length: 14 - values.length }, () => 0),
              ...values,
            ];
            return {
              today: "2026-11-17",
              days: 14,
              providers: [
                {
                  id: "claude",
                  name: "Claude Code",
                  found: true,
                  note: "",
                  today: 120000,
                  week: 900000,
                  month: 2400000,
                  models: [
                    { model: "claude-sonnet-5-5", tokens: 1800000 },
                    { model: "claude-haiku-5-5", tokens: 600000 },
                  ],
                  days: days([300000, 480000, 120000]),
                },
                {
                  id: "codex",
                  name: "Codex",
                  found: true,
                  note: "",
                  today: 0,
                  week: 40000,
                  month: 90000,
                  models: [{ model: "gpt-6-luna", tokens: 90000 }],
                  days: days([40000, 0, 0]),
                },
                {
                  id: "antigravity",
                  name: "Antigravity",
                  found: true,
                  note: "16 conversations on this computer. Antigravity keeps no token counts here, so its use cannot be shown.",
                  today: 0,
                  week: 0,
                  month: 0,
                  models: [],
                  days: days([]),
                },
                {
                  id: "opencode",
                  name: "OpenCode",
                  found: false,
                  note: "",
                  today: 0,
                  week: 0,
                  month: 0,
                  models: [],
                  days: days([]),
                },
              ],
            };
          }
          case "finance":
          case "finance_save": {
            const w = window as unknown as {
              __plans?: {
                currency: string;
                plans: {
                  name: string;
                  provider: string;
                  monthly: number;
                  per_million: number;
                }[];
                subs?: {
                  name: string;
                  store: string;
                  price: number;
                  period: string;
                  renews: string;
                  status: string;
                  link: string;
                }[];
                wallets?: {
                  name: string;
                  kind: string;
                  balance: number;
                  currency: string;
                  updated: string;
                  link: string;
                }[];
              };
            };
            if (args.method === "finance_save")
              w.__plans = args.params?.plans as typeof w.__plans;
            const plans = (w.__plans ??= {
              currency: "USD",
              plans: [
                {
                  name: "Claude Max",
                  provider: "claude",
                  monthly: 200,
                  per_million: 0,
                },
              ],
            });
            const tokens: Record<string, number> = {
              claude: 2400000,
              codex: 90000,
            };
            const rows = plans.plans.map((plan) => {
              const used = plan.per_million ? (tokens[plan.provider] ?? 0) : 0;
              const metered = (used / 1_000_000) * plan.per_million;
              return {
                ...plan,
                provider_name:
                  plan.provider === "codex" ? "Codex" : "Claude Code",
                tokens: used,
                metered,
                total: plan.monthly + metered,
              };
            });
            const stores: Record<string, string> = {
              apple: "https://apps.apple.com/account/subscriptions",
              google: "https://play.google.com/store/account/subscriptions",
              other: "",
            };
            const subs = (plans.subs ?? []).map((sub) => ({
              ...sub,
              state: sub.status,
              active: sub.status === "active",
              monthly: sub.period === "year" ? sub.price / 12 : sub.price,
              manage: stores[sub.store] ?? "",
              resubscribe: sub.link || (stores[sub.store] ?? ""),
            }));
            const walletPages: Record<string, string> = {
              paypal: "https://www.paypal.com/myaccount/summary",
            };
            const wallets = (plans.wallets ?? []).map((wallet) => ({
              ...wallet,
              open: wallet.link || (walletPages[wallet.kind] ?? ""),
            }));
            const walletTotals: Record<string, number> = {};
            for (const wallet of wallets)
              walletTotals[wallet.currency] =
                (walletTotals[wallet.currency] ?? 0) + wallet.balance;
            const subsMonthly = subs
              .filter((sub) => sub.active)
              .reduce((n, sub) => n + sub.monthly, 0);
            const fixed = rows.reduce((n, r) => n + r.monthly, 0) + subsMonthly;
            const metered = rows.reduce((n, r) => n + r.metered, 0);
            return {
              plans: {
                ...plans,
                subs: plans.subs ?? [],
                wallets: plans.wallets ?? [],
              },
              report: {
                currency: plans.currency,
                rows,
                subs,
                subs_monthly: subsMonthly,
                wallets,
                wallet_totals: walletTotals,
                fixed,
                metered,
                total: fixed + metered,
                projected: fixed + (metered / 17) * 30,
                day: 17,
                days_in_month: 30,
                daily: Array.from({ length: 14 }, () => 0),
              },
              providers: [
                { id: "claude", name: "Claude Code" },
                { id: "codex", name: "Codex" },
              ],
              currencies: ["USD", "EUR", "AED"],
            };
          }
          case "open_link": {
            const w = window as unknown as { __opened?: string[] };
            (w.__opened ??= []).push(String(args.params?.url));
            return { opened: args.params?.url };
          }
          case "vault_board":
          case "vault_insights_request": {
            const w = window as unknown as { __asked?: number };
            if (args.method === "vault_insights_request")
              w.__asked = (w.__asked ?? 0) + 1;
            return {
              sent: args.method === "vault_insights_request",
              stats: {
                notes: 42,
                links: 30,
                orphans: 5,
                broken: 1,
                important: 4,
                projects: 3,
                project_names: ["Alpha", "Beta", "Hippocampus"],
                daily: 12,
                memory: 6,
                tags: 9,
                top_tags: [
                  ["project", 3],
                  ["important", 4],
                ],
                folders: [
                  ["Projects", 10],
                  ["Daily", 12],
                ],
                changed_week: 7,
                recent: [
                  {
                    path: "Projects/Alpha/plan.md",
                    title: "Plan",
                    at: "2026-11-17T09:00",
                  },
                ],
              },
              insights: w.__asked
                ? {
                    summary:
                      "Three projects are active; Alpha has open to-dos.",
                    numbers: [{ label: "Open to-dos", value: "8", note: "" }],
                    highlights: ["Alpha/plan.md has 5 unchecked boxes"],
                    generated_at: "2026-11-17T10:00:00",
                  }
                : null,
            };
          }
          case "github_all":
            return {
              days: 30,
              others: [],
              repos: [
                {
                  repo: "me/hippocampus",
                  description: "The app",
                  private: true,
                  fork: false,
                  pushed: "2026-11-17T08:00:00Z",
                  language: "Svelte",
                  stars: 3,
                  agents: [
                    {
                      agent: "frank",
                      name: "Frank",
                      folder: "/w/frank",
                      commits: 4,
                      last: "2026-11-16",
                      subjects: ["Fix the tabs", "Add the calendar"],
                    },
                  ],
                },
                {
                  repo: "me/notes",
                  description: "",
                  private: false,
                  fork: false,
                  pushed: "2026-10-01T08:00:00Z",
                  language: "",
                  stars: 0,
                  agents: [],
                },
              ],
            };
          case "calendar":
          case "calendar_add":
          case "calendar_remove":
          case "calendar_mark": {
            type Ev = {
              id: string;
              date: string;
              time: string;
              title: string;
              note: string;
              agent: string;
              status: string;
              result: string;
            };
            const w = window as unknown as { __events?: Ev[] };
            const ev = (
              id: string,
              date: string,
              time: string,
              title: string,
              status: string,
              result = "",
            ): Ev => ({
              id,
              date,
              time,
              title,
              note: "",
              agent: "hippoherman",
              status,
              result,
            });
            const events = (w.__events ??= [
              ev("e1", "2026-11-20", "15:30", "Dentist", "scheduled"),
              ev(
                "e2",
                "2026-11-17",
                "09:00",
                "Send the weekly report",
                "done",
                "Sent it to the team.",
              ),
              ev(
                "e3",
                "2026-11-18",
                "11:30",
                "Renew the domain",
                "failed",
                "No card on file.",
              ),
              ev("e4", "2026-11-17", "14:00", "Review notes", "sent"),
            ]);
            if (args.method === "calendar_add") {
              if (String(args.params?.title) === "boom")
                throw new Error("An event needs a title.");
              events.push(
                ev(
                  `e${events.length + 1}`,
                  String(args.params?.date),
                  String(args.params?.time ?? ""),
                  String(args.params?.title),
                  "scheduled",
                ),
              );
            }
            if (args.method === "calendar_remove")
              events.splice(
                events.findIndex((event) => event.id === args.params?.id),
                1,
              );
            if (args.method === "calendar_mark") {
              const found = events.find(
                (event) => event.id === args.params?.id,
              );
              if (found) found.status = String(args.params?.status);
            }
            const month =
              args.method === "calendar_add"
                ? String(args.params?.date).slice(0, 7)
                : String(args.params?.month ?? "2026-11");
            const first = new Date(`${month}-01T00:00:00Z`);
            return {
              month,
              first_weekday: (first.getUTCDay() + 6) % 7,
              days: new Date(
                Date.UTC(first.getUTCFullYear(), first.getUTCMonth() + 1, 0),
              ).getUTCDate(),
              today: "2026-11-17",
              events: events.filter((event) => event.date.startsWith(month)),
              job_runs:
                month === "2026-11"
                  ? [{ date: "2026-11-19", name: "Weekly link check" }]
                  : [],
              upcoming: events
                .filter(
                  (event) =>
                    event.status === "sent" ||
                    (event.status === "scheduled" &&
                      event.date >= "2026-11-17"),
                )
                .sort((a, b) =>
                  (a.date + a.time).localeCompare(b.date + b.time),
                )
                .slice(0, 4),
              agents: ["hippoherman"],
            };
          }
          case "apps":
          case "app_connect":
          case "app_disconnect": {
            const w = window as unknown as {
              __apps?: Record<
                string,
                { hint: string; saved: Record<string, string> }
              >;
              __appKeys?: string[];
            };
            const on = (w.__apps ??= {});
            if (args.method === "app_connect") {
              const key = String(args.params?.key ?? "");
              const fields = (args.params?.fields ?? {}) as Record<
                string,
                string
              >;
              if (
                args.params?.id === "shopify" &&
                !/^[a-z0-9.-]+\.[a-z]+$/.test(fields.shop ?? "")
              )
                throw new Error(
                  "Shop address must look like my-shop.myshopify.com.",
                );
              // A test reads window.__appKeys to see the key reached the backend, and only there.
              (w.__appKeys ??= []).push(key);
              on[String(args.params?.id)] = {
                hint: key.slice(-4),
                saved: fields,
              };
            }
            if (args.method === "app_disconnect")
              Reflect.deleteProperty(on, String(args.params?.id));
            const catalogue = [
              {
                id: "shopify",
                name: "Shopify",
                what: "Orders, products and customers of your shop.",
                fields: [
                  {
                    key: "shop",
                    label: "Shop address",
                    example: "my-shop.myshopify.com",
                  },
                ],
                numbers: ["Orders", "Products", "Customers"],
              },
              {
                id: "builtbybit",
                name: "BuiltByBit",
                what: "Your resources and unread alerts.",
                fields: [],
                numbers: ["Your resources", "Unread alerts"],
              },
              {
                id: "stripe",
                name: "Stripe",
                what: "Balance, charges and customers.",
                fields: [],
                numbers: ["Available balance"],
              },
            ];
            return {
              network: "converse",
              apps: catalogue.map((app) => ({
                ...app,
                key_help: "An API key or access token with read access.",
                saved: on[app.id]?.saved ?? {},
                connected: app.id in on,
                hint: on[app.id]?.hint ?? null,
              })),
            };
          }
          case "app_board":
            return {
              id: args.params?.id,
              name: "Shopify",
              numbers: [
                { label: "Orders", value: "12", error: "" },
                { label: "Products", value: "40", error: "" },
                {
                  label: "Customers",
                  value: "",
                  error:
                    "The key may not read this (403). It needs read access.",
                },
              ],
            };
          case "phone_control": {
            if (args.params?.approve !== true)
              throw new Error("controlling a phone needs the user's approval");
            const w = window as unknown as { __controls?: unknown[] };
            (w.__controls ??= []).push(args.params?.action);
            return { ok: true };
          }
          case "phone_status":
          case "phone_mirror":
          case "phone_view":
          case "phone_stop": {
            const w = window as unknown as {
              __mirroring?: string[];
              __showing?: Record<string, string>;
            };
            w.__mirroring ??= [];
            w.__showing ??= {};
            if (args.method === "phone_view") {
              if (args.params?.approve !== true)
                throw new Error("mirroring a phone needs the user's approval");
              // A 1 by 1 picture stands in for the phone's stream.
              w.__showing[String(args.params?.serial)] =
                "data:image/gif;base64,R0lGODlhAQABAAAAACw=";
            }
            if (args.method === "phone_mirror") {
              if (args.params?.approve !== true)
                throw new Error("mirroring a phone needs the user's approval");
              w.__mirroring.push(String(args.params?.serial));
            }
            if (args.method === "phone_stop") {
              w.__mirroring = [];
              w.__showing = {};
            }
            return {
              adb: true,
              scrcpy: true,
              devices: [
                { serial: "R58M123ABC", state: "device", model: "SM A525F" },
                {
                  serial: "192.168.1.20:5555",
                  state: "unauthorized",
                  model: "",
                },
              ],
              mirroring: w.__mirroring,
              showing: w.__showing,
              error: "",
            };
          }
          case "github_board":
            if (String(args.params?.repo) === "nobody/nothing")
              return { error: "HTTP 404: Not Found" };
            return {
              repo: String(args.params?.repo),
              pulls: 2,
              drafts: 1,
              issues: 1,
              runs: 3,
              failed_runs: 1,
              running_runs: 1,
              newest_run: { name: "tests", branch: "main", state: "failed" },
              newest_pulls: [{ number: 7, title: "Add dashboards" }],
              newest_issues: [{ number: 3, title: "Graph is slow" }],
              capped: [],
            };
          case "ci":
            return { state: "failed", text: "tests on main: failure." };
          case "briefing_preview": {
            const text = `1. Role\nYou are ${String(args.params?.name)}, an agent in the Hippocampus app. Your goal: ${String(args.params?.goal)}.`;
            return { text, version: 5, characters: text.length };
          }
          case "agent_pins": {
            // Each pinned note costs 900 tokens here, so two pins pass the 1500 warning line.
            const row = (
              savedAgents as { id: string; pinned?: string[] }[]
            ).find((a) => a.id === args.params?.agent);
            const notes = (row?.pinned ?? []).map((path) => ({
              path,
              tokens: 900,
              cut: false,
              missing: "",
            }));
            const tokens = notes.length * 900;
            return { notes, tokens, warn: tokens > 1500, limit: 1500 };
          }
          case "terminal_rebrief": {
            const w = window as unknown as { __rebriefed?: string[] };
            (w.__rebriefed ??= []).push(String(args.params?.agent));
            return { path: "/home/me/.hippocampus/briefings/agent.md" };
          }
          case "webhooks":
            return { webhooks: hookRows };
          case "save_webhook":
            hookRows.push({
              id: `hook-${hookRows.length + 1}`,
              name: String(args.params?.name),
              kind: String(args.params?.kind),
            });
            return { webhooks: hookRows };
          case "run_webhook":
            if (args.params?.approve !== true)
              throw new Error("needs approval");
            return { result: "Link check: 3 links checked, all working." };
          case "delete_webhook": {
            const at = hookRows.findIndex((h) => h.id === args.params?.id);
            if (at < 0) throw new Error("no webhook with that id");
            hookRows.splice(at, 1);
            return { webhooks: hookRows };
          }
          case "connectors":
            return { connectors: connectorRows };
          case "jobs":
            return { jobs: jobRows };
          case "set_job": {
            const [job] = jobRows;
            if (!job) throw new Error("mock: no job");
            job.enabled = Boolean(args.params?.enabled);
            if (args.params?.every_days)
              job.every_days = Number(args.params.every_days);
            return { jobs: jobRows };
          }
          case "run_job": {
            const [job] = jobRows;
            if (!job) throw new Error("mock: no job");
            if (args.params?.approve !== true)
              throw new Error("needs approval");
            job.last_run = "2026-11-15T09:00:00";
            return {
              jobs: jobRows,
              result: `${job.name}: 3 links checked, all working.`,
            };
          }
          case "missions":
            return { missions: missionRows, cap: 20 };
          case "mission_save": {
            const row = args.params?.mission as Record<string, unknown>;
            if (!String(row.label ?? "").trim())
              throw new Error("The label must be 1 to 60 characters.");
            const id = String(row.id ?? `mission-${missionRows.length + 1}`);
            const saved = {
              id,
              label: String(row.label),
              message: String(row.message),
              agent: String(row.agent),
              every_minutes: (row.every_minutes as number | undefined) ?? null,
              days: (row.days as number[] | undefined) ?? [],
              at: String(row.at ?? ""),
              enabled: row.enabled === true,
              last_run: null,
            };
            missionRows = row.id
              ? missionRows.map((m) => (m.id === id ? saved : m))
              : [...missionRows, saved];
            return { missions: missionRows, cap: 20 };
          }
          case "mission_remove":
            missionRows = missionRows.filter((m) => m.id !== args.params?.id);
            return { missions: missionRows, cap: 20 };
          case "helpers":
            return { helpers: helperRows, limit: 4 };
          case "start_helper": {
            const parts = args.params?.parts as
              { objective?: string } | undefined;
            const prompt = String(
              args.params?.prompt ?? parts?.objective ?? "",
            );
            if (!prompt.trim()) throw new Error('"prompt" is empty');
            helperRows = [
              ...helperRows,
              {
                id: helperRows.length + 1,
                prompt,
                status: "running",
                result: "",
              },
            ];
            return { helpers: helperRows, limit: 4 };
          }
          case "skills":
            return { skills: skillRows };
          case "open_skill_folder":
            return { skills: skillRows };
          case "remove_skill":
            skillRows = skillRows.filter((k) => k.name !== args.params?.name);
            return { skills: skillRows };
          case "install_skill": {
            const path = String(args.params?.path ?? "");
            if (path.includes("slow"))
              await new Promise((r) => setTimeout(r, 4000));
            const name = path.split("/").pop() ?? "";
            skillRows = [
              ...skillRows,
              { name, description: "Installed from a folder", path },
            ];
            return { skills: skillRows };
          }
          case "keys":
            return { keys: keyRows() };
          case "save_key":
            if (String(args.params?.provider) === "claude")
              claudeKey = String(args.params?.key);
            return { keys: keyRows() };
          case "clear_key":
            if (String(args.params?.provider) === "claude") claudeKey = null;
            return { keys: keyRows() };
          case "link_doctor":
            return {
              notes: 3,
              broken_count: 1,
              lonely_count: 1,
              broken: [{ note: "Alpha.md", link: "Missing note" }],
              lonely: ["Gamma.md"],
            };
          case "settings_export":
            return { text: '[network]\nmode = "ask"\n', path: "/mock" };
          case "settings_import":
            if (!String(args.params?.text).includes("["))
              throw new Error("This is not a settings file: no section found");
            return { imported: true, restart: "Restart the app." };
          case "doctor":
            return {
              checks: [
                {
                  name: "Backend",
                  state: "ok",
                  found: "Running, version 0.1.0.",
                  fix: "",
                },
                {
                  name: "Codex program",
                  state: "bad",
                  found: "Installed, but not signed in.",
                  fix: "Run `codex login` in a terminal.",
                },
                {
                  name: "Agent sandbox",
                  state: "warn",
                  found: "bubblewrap cannot start here.",
                  fix: "Install bubblewrap.",
                },
              ],
              summary: { ok: 1, warn: 1, bad: 1 },
            };
          case "terminal_traces":
            return {
              traces: [
                {
                  at: "2026-11-12T10:01:00Z",
                  tool: "Bash",
                  detail: "rm notes.md",
                  status: "failed",
                },
                {
                  at: "2026-11-12T10:00:00Z",
                  tool: "mcp__vault__read_note",
                  detail: "MAIN.md",
                  status: "done",
                },
              ],
            };
          case "terminal_command":
            // No program is running in tests; the id says which run of the backend answered.
            // A test sets window.__cliCommand to act out a CLI running in every terminal.
            return {
              command:
                (window as unknown as { __cliCommand?: string }).__cliCommand ??
                null,
              status: null,
              boot: bootId(),
              // A test sets window.__crashed to act out a CLI that ended with an error.
              crashed:
                (window as unknown as { __crashed?: number }).__crashed ?? null,
              // A test sets window.__delivery to act out how the briefing reached the CLI.
              delivery:
                (window as unknown as { __delivery?: string }).__delivery ??
                null,
            };
          default:
            throw new Error(`mock: unknown method ${args.method}`);
        }
      }

      Object.assign(window, {
        __TAURI_EVENT_PLUGIN_INTERNALS__: { unregisterListener: () => {} },
        __TAURI_INTERNALS__: {
          metadata: {
            currentWindow: { label: "main" },
            currentWebview: { label: "main", windowLabel: "main" },
          },
          transformCallback: (callback: (payload: unknown) => void) => {
            const id = nextId++;
            callbacks.set(id, callback);
            return id;
          },
          unregisterCallback: (id: number) => callbacks.delete(id),
          invoke: async (cmd: string, args: Record<string, unknown> = {}) => {
            if (cmd === "plugin:event|listen") {
              const name = args.event as string;
              listeners.set(name, [
                ...(listeners.get(name) ?? []),
                args.handler as number,
              ]);
              return args.handler;
            }
            if (cmd === "plugin:event|unlisten") return undefined;
            if (cmd === "sidecar_call")
              return sidecarCall(
                args as { method: string; params?: Record<string, unknown> },
              );
            throw new Error(`mock: unknown command ${cmd}`);
          },
        },
      });
    },
    {
      orphan: options.orphan === true,
      noVault: options.noVault === true,
      signedIn: options.signedIn === true,
      account: options.account === true,
      intro: options.intro === true,
      firstRun: options.firstRun === true,
      fail: options.fail ?? [],
    },
  );
}
