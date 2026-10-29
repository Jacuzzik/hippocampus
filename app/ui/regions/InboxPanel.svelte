<!-- Every agent's inbox, read only: pending messages first, then handled ones, as in Munder Difflin's Inbox page. -->
<script lang="ts">
  import { onMount } from "svelte";
  import { invoke } from "@tauri-apps/api/core";

  type Message = {
    id: string;
    from: string | null;
    to: string | null;
    act: string | null;
    subject: string | null;
    created_at: string | null;
    state: "pending" | "done";
  };

  let messages = $state<Message[]>([]);
  let failed = $state(false);

  onMount(async () => {
    try {
      messages = (await invoke<{ messages: Message[] }>("sidecar_call", { method: "inbox" })).messages;
    } catch (cause) {
      failed = true;
      console.error("Could not read the inboxes", cause);
    }
  });
</script>

<section class="inbox" aria-label="Inbox">
  {#if failed}
    <p class="muted">Could not read the inboxes.</p>
  {:else if messages.length === 0}
    <p class="muted">No messages yet.</p>
  {:else}
    <ul>
      {#each messages as message (message.id)}
        <li>
          <span class="state {message.state}">{message.state}</span>
          <span class="route">{message.from ?? "?"} → {message.to ?? "?"}</span>
          <span class="subject">{message.subject ?? message.act ?? ""}</span>
          <small>{message.created_at ?? ""}</small>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .inbox {
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
    color: var(--color-md-text);
    overflow-y: auto;
  }

  ul {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: baseline;
    padding: var(--space-1) 0;
    border-bottom: 1px solid var(--color-border);
  }

  .state {
    color: var(--color-md-accent);
  }

  .state.done {
    color: var(--color-md-text-subtle);
  }

  .route {
    color: var(--color-md-text-muted);
  }

  li small {
    margin-left: auto;
    color: var(--color-md-text-subtle);
  }

  .muted {
    color: var(--color-md-text-muted);
  }
</style>
