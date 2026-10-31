<!-- The right-panel tab for a selected added agent: its header, its own chat, and the card menu's actions. -->
<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import type { Message } from "../assistant/model";
  import { archiveAgent, removeAgent, startEdit, type SavedAgent } from "./addedAgents.svelte";

  let { agent }: { agent: SavedAgent } = $props();

  interface SavedSession {
    session: string;
    messages: Message[];
  }

  // Not reported until the app has a real status and the user decides how to show it.
  const NOT_REPORTED = "Not reported";

  let sessions = $state<SavedSession[]>([]);
  let messages = $state<Message[]>([]);
  let text = $state("");
  let busy = $state(false);
  let error = $state<string | null>(null);

  // Each added agent has its own Claude Code session; the sidecar keeps the sessions and their chat.
  onMount(async () => {
    try {
      const saved = await invoke<{ sessions: SavedSession[] }>("sidecar_call", {
        method: "chat_history",
        params: { agent: agent.id },
      });
      sessions = saved.sessions;
      if (sessions.length === 0) {
        const created = await invoke<{ session: string }>("sidecar_call", {
          method: "agent_session",
          params: { agent: agent.id },
        });
        sessions = [{ session: created.session, messages: [] }];
      }
      messages = sessions[sessions.length - 1]?.messages ?? [];
    } catch (cause) {
      error = String(cause);
    }
  });

  function save(): void {
    const last = sessions.length - 1;
    const next = last < 0 ? [{ session: "", messages }] : sessions.map((s, i) => (i === last ? { ...s, messages } : s));
    sessions = next;
    invoke("sidecar_call", {
      method: "chat_history_save",
      params: { agent: agent.id, sessions: next },
    }).catch((cause) => console.error("Could not save the agent's chat", cause));
  }

  async function send(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || busy) return;
    text = "";
    busy = true;
    error = null;
    messages = [...messages, { role: "user", text: trimmed }];
    try {
      const result = await invoke<{ reply: string; stopped: boolean }>("sidecar_call", {
        method: "chat",
        params: { chat: Date.now(), text: trimmed, continue: false, agent: agent.id },
      });
      messages = [
        ...messages,
        result.stopped
          ? { role: "error", text: "Stopped." }
          : { role: "assistant", text: result.reply || "(no reply)" },
      ];
    } catch (cause) {
      messages = [...messages, { role: "error", text: String(cause) }];
    } finally {
      busy = false;
      save();
    }
  }
</script>

<div class="agent-panel">
  <header>
    <div class="title">
      <b>{agent.name}</b>
      <span class="status">{NOT_REPORTED}</span>
    </div>
    <div class="icons">
      <button type="button" aria-label="Rename" onclick={() => startEdit(agent.id, "rename")}>Edit</button>
      <button type="button" class="danger" onclick={() => archiveAgent(agent.id)}>Archive</button>
      <button type="button" class="danger" onclick={() => removeAgent(agent.id)}>Delete</button>
    </div>
  </header>

  <p class="meta">
    <span>{agent.model || "No model set"}</span>
    <span>{agent.folder || "No folder"}</span>
  </p>

  <!-- Dummy controls for now: they do nothing until their behaviour is decided. -->
  <div class="tabs" role="group" aria-label="Agent views">
    <button type="button" aria-pressed="true">Terminal</button>
    <button type="button" aria-pressed="false">Git</button>
    <button type="button" aria-pressed="false">Messages</button>
    <button type="button" aria-pressed="false">Traces</button>
  </div>
  <div class="controls" role="group" aria-label="Agent controls">
    <button type="button">Block tools</button>
    <button type="button">Stop after this step</button>
    <button type="button">1:1</button>
  </div>

  <div class="chat" aria-label="Chat with {agent.name}">
    {#if error}<p class="error" role="alert">{error}</p>{/if}
    <ol>
      {#each messages as message, index (index)}
        <li class={message.role}>{message.text}</li>
      {/each}
    </ol>
    <form onsubmit={send}>
      <input type="text" bind:value={text} placeholder={`Message ${agent.name}`} aria-label={`Message ${agent.name}`} />
      <button type="submit" disabled={busy || !text.trim()}>{busy ? "Working…" : "Send"}</button>
    </form>
  </div>

  <div class="actions">
    <button type="button" onclick={() => startEdit(agent.id, "note")}>Add note</button>
    {#if agent.note}<p class="note">{agent.note}</p>{/if}
  </div>
</div>

<style>
  .agent-panel {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    padding: var(--space-2);
    color: var(--color-md-text);
    font-size: var(--font-size-xs);
  }
  header {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
  }
  .title {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }
  .title b {
    font-size: 14px;
  }
  .status {
    padding: 0 var(--space-1);
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
    color: var(--color-md-text-muted);
  }
  .meta {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin: 0;
    color: var(--color-md-text-muted);
  }
  .icons,
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
  }
  button {
    min-height: 44px;
    padding: 0 var(--space-2);
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
    background: var(--color-md-surface);
    color: var(--color-md-text);
    cursor: pointer;
  }
  .danger {
    color: var(--color-danger);
  }
  .chat ol {
    display: grid;
    gap: var(--space-1);
    margin: 0;
    padding: 0;
    list-style: none;
  }
  .chat li {
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
  .chat li.user {
    color: var(--color-md-text-muted);
  }
  .chat li.error,
  .error {
    color: var(--color-danger);
  }
  .chat form {
    display: flex;
    gap: var(--space-1);
    margin-top: var(--space-2);
  }
  .chat input {
    flex: 1;
    min-width: 0;
    min-height: 44px;
    padding: 0 var(--space-2);
    color: inherit;
    background: var(--color-md-surface);
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
  }
  .tabs,
  .controls {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
  }
  .tabs button[aria-pressed="true"] {
    border-color: var(--color-md-text);
  }
  .note {
    margin: 0;
    white-space: pre-wrap;
    overflow-wrap: anywhere;
  }
</style>
