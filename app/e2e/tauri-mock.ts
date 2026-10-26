// Only the part of Playwright's Page this file uses, so the app can import it without Playwright.
type Page = { addInitScript(fn: () => void): Promise<unknown> | unknown };

// Stands in for the Tauri bridge and the Python sidecar. It answers the same requests with the
// same shapes as core/__main__.py, so the UI runs unchanged. The Python side has its own tests.
export async function mockSidecar(page: Page): Promise<void> {
  await page.addInitScript(() => {
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
      params: { chat: number; text: string };
    }): Promise<unknown> {
      const { chat, text } = args.params;
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

    async function sidecarCall(args: {
      method: string;
      params?: Record<string, unknown>;
    }): Promise<unknown> {
      switch (args.method) {
        case "graph":
          return graph;
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
  });
}
