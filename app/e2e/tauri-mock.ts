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
          case "account":
            return { claude: claudeKey !== null };
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
