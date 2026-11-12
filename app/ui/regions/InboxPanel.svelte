<!-- Messages between this app's agents: conversations grouped by thread, with state, filters, search and a box to write one. -->
<script lang="ts">
  import { onMount } from "svelte";
  import { every } from "../poll.ts";
  import { flagOn } from "../flags.svelte.ts";
  import { invoke } from "@tauri-apps/api/core";
  import Dropdown from "../controls/Dropdown.svelte";
  import EmptyState from "../controls/EmptyState.svelte";
  import { addedAgents, archived } from "../owner/addedAgents.svelte";

  type Message = {
    id: string;
    from: string | null;
    to: string | null;
    act: string | null;
    subject: string | null;
    body: string | null;
    work: string | null;
    thread: string;
    priority: string | null;
    created_at: string | null;
    state: "queued" | "delivered" | "failed" | "dropped";
    failed?: string | null;
  };

  // What each state means, in the words the list shows.
  const STATE_TEXT: Record<Message["state"], string> = {
    queued: "waiting",
    delivered: "delivered",
    failed: "not sent",
    dropped: "dropped",
  };

  let messages = $state<Message[]>([]);
  let failed = $state(false);
  let query = $state("");
  let agentFilter = $state("all");
  let stateFilter = $state("all");
  let openThread = $state<string | null>(null);

  // Read again every few seconds while this tab is open, so it does not go stale.
  async function load(): Promise<void> {
    try {
      const words = query.trim();
      messages = (
        await invoke<{ messages: Message[] }>(
          "sidecar_call",
          words
            ? { method: "inbox_search", params: { query: words } }
            : { method: "inbox" },
        )
      ).messages;
      failed = false;
    } catch (cause) {
      failed = true;
      console.error("Could not read the inboxes", cause);
    }
  }
  onMount(() => {
    void load();
    return flagOn("panelRefresh") ? every(load, 5000) : undefined;
  });

  const agents = $derived([
    "hippoherman",
    ...addedAgents.list
      .filter((a) => !archived.ids.includes(a.id))
      .map((a) => a.id),
  ]);
  const agentOptions = $derived([
    { value: "all", label: "All agents" },
    ...agents.map((id) => ({ value: id, label: id })),
  ]);
  const STATE_OPTIONS = [
    { value: "all", label: "Any state" },
    { value: "queued", label: "Waiting" },
    { value: "delivered", label: "Delivered" },
    { value: "failed", label: "Not sent" },
    { value: "dropped", label: "Dropped" },
  ];

  const shown = $derived(
    messages.filter(
      (m) =>
        (agentFilter === "all" ||
          m.from === agentFilter ||
          m.to === agentFilter) &&
        (stateFilter === "all" || m.state === stateFilter),
    ),
  );
  // One row per conversation, newest conversation first; the messages inside run oldest first.
  const threads = $derived.by(() => {
    const groups: Record<string, Message[]> = {};
    for (const message of shown) (groups[message.thread] ??= []).push(message);
    return Object.entries(groups).flatMap(([id, list]) => {
      const ordered = [...list].sort((a, b) =>
        String(a.created_at).localeCompare(String(b.created_at)),
      );
      const first = ordered[0];
      const last = ordered[ordered.length - 1];
      if (!first || !last) return [];
      return [
        {
          id,
          list: ordered,
          first,
          last,
          waiting: ordered.filter((m) => m.state === "queued").length,
        },
      ];
    });
  });
  const waitingTotal = $derived(
    messages.filter((m) => m.state === "queued").length,
  );
  const when = (value: string | null): string =>
    (value ?? "").replace("T", " ").slice(0, 16);

  // The box to write a message as yourself, to one agent or to all of them.
  let to = $state("all");
  let subject = $state("");
  let body = $state("");
  let urgent = $state(false);
  let sendNote = $state<string | null>(null);
  let sendError = $state<string | null>(null);
  const toOptions = $derived([
    { value: "all", label: "All agents" },
    ...agents.map((id) => ({ value: id, label: id })),
  ]);
  async function send(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    sendNote = sendError = null;
    try {
      const sent = await invoke<{ ids: string[] }>("sidecar_call", {
        method: "task_send",
        params: {
          to,
          from: "user",
          subject: subject.trim(),
          body: body.trim(),
          priority: urgent ? "urgent" : "normal",
        },
      });
      sendNote =
        sent.ids.length === 1
          ? "Message queued."
          : `Message queued for ${sent.ids.length} agents.`;
      subject = body = "";
      urgent = false;
      await load();
    } catch (cause) {
      sendError = String(cause);
    }
  }

  // Copies one conversation as Markdown, to paste into a note.
  let copied = $state<string | null>(null);
  async function exportThread(id: string): Promise<void> {
    try {
      const found = await invoke<{ markdown: string }>("sidecar_call", {
        method: "inbox_thread",
        params: { thread: id },
      });
      await navigator.clipboard.writeText(found.markdown);
      copied = id;
    } catch (cause) {
      sendError = String(cause);
    }
  }
</script>

<section class="inbox" aria-label="Inbox">
  <form class="compose" aria-label="Write a message" onsubmit={send}>
    <div class="row">
      <Dropdown options={toOptions} bind:value={to} label="Send to" />
      <label class="urgent"
        ><input type="checkbox" bind:checked={urgent} /> urgent</label
      >
    </div>
    <input
      type="text"
      aria-label="Subject"
      placeholder="Subject"
      maxlength="200"
      bind:value={subject}
    />
    <textarea
      rows="2"
      aria-label="Message text"
      placeholder="Message to your agents"
      bind:value={body}></textarea>
    <button
      type="submit"
      class="primary"
      disabled={!subject.trim() && !body.trim()}>Send message</button
    >
    {#if sendNote}<p class="muted" role="status">{sendNote}</p>{/if}
    {#if sendError}<p class="error" role="alert">{sendError}</p>{/if}
  </form>

  <div class="filters">
    <input
      type="search"
      aria-label="Search messages"
      placeholder="Search messages"
      bind:value={query}
      oninput={() => void load()}
    />
    <Dropdown
      options={agentOptions}
      bind:value={agentFilter}
      label="Filter by agent"
    />
    <Dropdown
      options={STATE_OPTIONS}
      bind:value={stateFilter}
      label="Filter by state"
    />
  </div>
  <p class="muted" aria-live="polite">
    {waitingTotal} waiting · {threads.length}
    {threads.length === 1 ? "conversation" : "conversations"}
  </p>

  {#if failed}
    <EmptyState
      title="Could not read the inboxes"
      text="The backend did not answer. It is asked again in a few seconds."
    />
  {:else if threads.length === 0}
    <EmptyState
      title={messages.length === 0 && !query.trim()
        ? "No messages yet"
        : "No message matches"}
      text={messages.length === 0 && !query.trim()
        ? "Messages your agents send each other show here, grouped by conversation. Write one above to start."
        : "Change the search or the filters to see more."}
    />
  {:else}
    <ul class="threads">
      {#each threads as thread (thread.id)}
        <li>
          <button
            type="button"
            class="thread"
            aria-expanded={openThread === thread.id}
            onclick={() =>
              (openThread = openThread === thread.id ? null : thread.id)}
          >
            <span class="subject"
              >{thread.first.subject ||
                thread.first.act ||
                "(no subject)"}</span
            >
            {#if thread.waiting > 0}<span class="badge"
                >{thread.waiting} waiting</span
              >{/if}
            <span class="route"
              >{thread.first.from ?? "?"} → {thread.first.to ?? "?"} · {thread
                .list.length}</span
            >
            <small>{when(thread.last.created_at)}</small>
          </button>
          {#if openThread === thread.id}
            <ol class="messages">
              {#each thread.list as message (message.id + message.state)}
                <li>
                  <div class="meta">
                    <span class="state {message.state}"
                      >{STATE_TEXT[message.state]}</span
                    >
                    <span class="act"
                      >{message.act ?? "request"}{message.priority === "urgent"
                        ? " · urgent"
                        : ""}</span
                    >
                    <span class="route"
                      >{message.from ?? "?"} → {message.to ?? "?"}</span
                    >
                    {#if message.work}<span class="route"
                        >task {message.work}</span
                      >{/if}
                    <small>{when(message.created_at)}</small>
                  </div>
                  {#if message.subject}<b>{message.subject}</b>{/if}
                  {#if message.body}<p>{message.body}</p>{/if}
                  {#if message.failed}<p class="error">
                      Not sent: {message.failed}
                    </p>{/if}
                </li>
              {/each}
            </ol>
            <button
              type="button"
              class="export"
              onclick={() => void exportThread(thread.id)}
            >
              {copied === thread.id
                ? "Copied"
                : "Copy conversation as Markdown"}
            </button>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .inbox {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    font-family: var(--font-ui);
    font-size: var(--font-size-xs);
    color: var(--color-md-text);
    overflow-y: auto;
  }

  .compose,
  .filters {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .row {
    display: flex;
    gap: var(--space-2);
    align-items: center;
  }

  .urgent {
    display: inline-flex;
    gap: var(--space-1);
    align-items: center;
    color: var(--color-md-text-muted);
  }

  input[type="text"],
  input[type="search"],
  textarea {
    width: 100%;
    min-height: 32px;
    padding: var(--space-1) var(--space-2);
    color: var(--color-md-text);
    font: inherit;
    background: var(--color-md-surface);
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
  }

  textarea {
    resize: vertical;
  }

  button {
    min-height: 32px;
    padding: 0 var(--space-2);
    color: var(--color-md-text);
    font: inherit;
    background: var(--color-md-surface);
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
    cursor: pointer;
  }

  button:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .primary {
    color: var(--color-md-accent-on);
    background: var(--color-md-accent);
    border-color: var(--color-md-accent);
  }

  ul,
  ol {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .thread {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: baseline;
    width: 100%;
    padding: var(--space-1) var(--space-2);
    text-align: left;
    background: none;
    border: none;
    border-bottom: 1px solid var(--color-md-border);
    border-radius: 0;
  }

  .thread .subject {
    flex: 1 1 60%;
    min-width: 0;
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .badge {
    padding: 0 var(--space-1);
    color: var(--color-md-accent);
    border: 1px solid currentColor;
    border-radius: var(--radius-sm);
  }

  .messages {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding: var(--space-2);
    border-bottom: 1px solid var(--color-md-border);
  }

  .messages p {
    margin: 0;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }

  .meta {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: baseline;
  }

  .state {
    color: var(--color-md-text-subtle);
  }

  .state.queued {
    color: var(--color-md-accent);
  }

  .state.failed,
  .error {
    color: var(--color-danger);
  }

  .route,
  .act {
    color: var(--color-md-text-muted);
  }

  small {
    margin-left: auto;
    color: var(--color-md-text-subtle);
  }

  .export {
    margin: var(--space-1) var(--space-2) var(--space-2);
  }

  .muted {
    margin: 0;
    color: var(--color-md-text-muted);
  }

  .error {
    margin: 0;
  }
</style>
