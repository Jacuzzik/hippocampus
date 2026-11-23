<script lang="ts">
  // Your cards (N.10): cards made from text selected in a note (Make card in the note editor) or by
  // the main agent. Each keeps its link back, and Open note makes or updates its own page in the
  // vault's Cards folder and opens it in the graph.
  import PanelHeader from "../controls/PanelHeader.svelte";
  import { invoke } from "@tauri-apps/api/core";
  import { onChanged } from "../changed.ts";
  import { onMount } from "svelte";

  type Card = {
    id: string;
    title: string;
    body: string;
    source?: string;
    note?: string;
  };
  let cards = $state<Card[]>([]);
  let error = $state<string | null>(null);

  async function load(): Promise<void> {
    try {
      cards = (
        await invoke<{ cards: Card[] }>("sidecar_call", { method: "cards" })
      ).cards;
      error = null;
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
{#if cards.length === 0}
  <p class="muted">
    None yet. Select text while editing a note and press Make card.
  </p>
{:else}
  <ul aria-label="Your cards">
    {#each cards as card (card.id)}
      <li>
        <span>{card.title}</span>
        {#if card.source}<small>from {card.source}</small>{/if}
        <button type="button" class="temp" onclick={() => openNote(card)}
          >{card.note ? "Open note" : "Make note"}</button
        >
      </li>
    {/each}
  </ul>
{/if}
{#if error}<p class="muted" role="alert">{error}</p>{/if}
