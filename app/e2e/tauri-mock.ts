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
  options: { orphan?: boolean; noVault?: boolean; signedIn?: boolean } = {},
): Promise<void> {
  await page.addInitScript(
    (opts: { orphan: boolean; noVault: boolean; signedIn: boolean }) => {
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
      // The Claude key is kept here, never sent back to the page: account reports only yes or no.
      let claudeKey: string | null = opts.signedIn ? "sk-saved" : null;

      // The note text the drawer reads through the "read" method.
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
          path: "/home/thalha/hippocampus/skills/tidy-notes",
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
        switch (args.method) {
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
                { id: "MDF-1", title: "Ship the Tasks page", status: "doing", assignee: "hippo", updatedAt: null },
                { id: "MDF-2", title: "Check the Inbox feed", status: "todo", assignee: null, updatedAt: null },
              ],
            };
          case "account":
            return {
              claude: claudeKey !== null,
              model: claudeKey !== null ? "claude-sonnet-5-5" : "qwen2.5:1.5b",
            };
          case "sign_in":
            if (!String(args.params?.key ?? "").trim())
              throw new Error('"sign_in" needs a non-empty "key"');
            claudeKey = String(args.params?.key).trim();
            return { claude: true };
          case "sign_out":
            claudeKey = null;
            return { claude: false };
          case "read": {
            const path = String(args.params?.path);
            if (!(path in texts)) throw new Error(`mock: no note ${path}`);
            return { id: path, text: texts[path] };
          }
          case "chat":
            return chat(
              args as unknown as { params: { chat: number; text: string } },
            );
          case "confirm": {
            const params = args.params as { call: string; approve: boolean };
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
            return { caps: budgetCaps, used: budgetUsed, allowance };
          case "set_budget":
            budgetCaps = args.params as typeof budgetCaps;
            return { caps: budgetCaps, used: budgetUsed, allowance };
          case "budget_allow":
            allowance = true;
            return { allowance: true };
          case "activity":
            return { rows: activityRows };
          case "asks":
            return {
              asks: [
                {
                  call: "ask-1",
                  question: "Which folder should the new note go in?",
                },
              ],
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
          case "helpers":
            return { helpers: helperRows, limit: 4 };
          case "start_helper":
            if (!String(args.params?.prompt ?? "").trim())
              throw new Error('"prompt" is empty');
            helperRows = [
              ...helperRows,
              {
                id: helperRows.length + 1,
                prompt: String(args.params?.prompt),
                status: "running",
                result: "",
              },
            ];
            return { helpers: helperRows, limit: 4 };
          case "skills":
            return { skills: skillRows };
          case "open_skill_folder":
            return { skills: skillRows };
          case "remove_skill":
            skillRows = skillRows.filter((k) => k.name !== args.params?.name);
            return { skills: skillRows };
          case "share":
            throw new Error("Not set up: no share host is configured.");
          case "keys":
            return { keys: keyRows() };
          case "save_key":
            if (String(args.params?.provider) === "claude")
              claudeKey = String(args.params?.key);
            return { keys: keyRows() };
          case "clear_key":
            if (String(args.params?.provider) === "claude") claudeKey = null;
            return { keys: keyRows() };
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
    },
  );
}
