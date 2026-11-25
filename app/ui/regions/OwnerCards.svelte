<script lang="ts">
  // Your cards (N.10): cards made from text selected in a note (Make card in the note editor) or by
  // the main agent. Each keeps its link back, and Open note makes or updates its own page in the
  // vault's Cards folder and opens it in the graph.
  import PanelHeader from "../controls/PanelHeader.svelte";
  import { invoke } from "@tauri-apps/api/core";
  import { onChanged } from "../changed.ts";
  import { onMount } from "svelte";
  import { call } from "../settings/call.ts";

  type Card = {
    id: string;
    title: string;
    body: string;
    source?: string;
    note?: string;
  };
  let cards = $state<Card[]>([]);
  let error = $state<string | null>(null);
  let loaded = $state(false);
  let title = $state("");
  let body = $state("");
  let editing = $state<string | null>(null);
  let editTitle = $state("");
  let editBody = $state("");

  async function load(): Promise<void> {
    try {
      cards = (await call<{ cards: Card[] }>("cards")).cards;
      error = null;
    } catch (cause) {
      error = String(cause);
    } finally {
      loaded = true;
    }
  }

  async function create(): Promise<void> {
    try {
      await call("card_create", { title, body });
      title = "";
      body = "";
      await load();
    } catch (cause) {
      error = String(cause);
    }
  }

  async function save(card: Card): Promise<void> {
    try {
      await call("card_update", {
        id: card.id,
        title: editTitle,
        body: editBody,
      });
      editing = null;
      await load();
    } catch (cause) {
      error = String(cause);
    }
  }
  onMount(() => onChanged("cards", load, 60000));
  onMount(() => void load());

  async function openNote(card: Card): Promise<void> {
    try {
      const answer = await invoke<{ note: string }>("sidecar_call", {
        method: "card_note",
        params: { id: card.id },
      });
      window.dispatchEvent(
        new CustomEvent("open-note", { detail: answer.note }),
      );
      void load();
    } catch (cause) {
      error = String(cause);
    }
  }
</script>

<PanelHeader title="YOUR CARDS" aside={String(cards.length)} />
<form class="new-card" onsubmit={(event) => { event.preventDefault(); void create(); }}>
  <input aria-label="Card title" placeholder="Card title" bind:value={title} required maxlength="200" />
  <textarea aria-label="Card details" placeholder="Card details" bind:value={body} required maxlength="10000"></textarea>
  <button type="submit" disabled={!title.trim() || !body.trim()}>Add card</button>
</form>
{#if !loaded}
  <p class="muted">Checking…</p>
{:else if cards.length === 0}
  <p class="muted">
    None yet. Select text while editing a note and press Make card.
  </p>
{:else}
  <ul aria-label="Your cards">
    {#each cards as card (card.id)}
      <li>
        {#if editing === card.id}
          <input aria-label="Edit card title" bind:value={editTitle} />
          <textarea aria-label="Edit card details" bind:value={editBody}></textarea>
          <button type="button" onclick={() => void save(card)}>Save</button>
          <button type="button" onclick={() => (editing = null)}>Cancel</button>
        {:else}
        <span>{card.title}</span>
        {#if card.source}<small>from {card.source}</small>{/if}
        <button type="button" class="temp" onclick={() => { editing = card.id; editTitle = card.title; editBody = card.body; }}>Edit</button>
        <button type="button" class="temp" onclick={() => openNote(card)}
          >{card.note ? "Open note" : "Make note"}</button
        >
        {/if}
      </li>
    {/each}
  </ul>
{/if}
{#if error}<p class="muted" role="alert">{error}</p>{/if}

<style>
  .new-card { display: grid; gap: var(--space-2); margin-block: var(--space-2); }
  .new-card input, .new-card textarea { min-width: 0; padding: var(--space-2); color: var(--color-md-text); background: var(--color-surface); border: 1px solid var(--color-border); border-radius: var(--radius-sm); font: inherit; }
  .new-card textarea { min-height: 4rem; resize: vertical; }
</style>
