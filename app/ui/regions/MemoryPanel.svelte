<!-- Each agent's memory notes, read only: size and last update, newest first. -->
<script lang="ts">
  import { onMount } from "svelte";
  import { invoke } from "@tauri-apps/api/core";

  type Note = { agent: string; bytes: number; updated_at: string };

  let notes = $state<Note[]>([]);
  let failed = $state(false);

  onMount(async () => {
    try {
      notes = (await invoke<{ notes: Note[] }>("sidecar_call", { method: "memory" })).notes;
    } catch (cause) {
      failed = true;
      console.error("Could not read the memory notes", cause);
    }
  });
</script>

<section class="memory" aria-label="Memory">
  {#if failed}
    <p class="muted">Could not read the memory notes.</p>
  {:else if notes.length === 0}
    <p class="muted">No memory notes yet.</p>
  {:else}
    <ul>
      {#each notes as note (note.agent)}
        <li>
          <span class="agent">{note.agent}</span>
          <small>{(note.bytes / 1024).toFixed(1)} KB · {note.updated_at.replace("T", " ")}</small>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .memory {
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

  .agent {
    color: var(--color-md-accent);
  }

  li small {
    margin-left: auto;
    color: var(--color-md-text-muted);
  }

  .muted {
    color: var(--color-md-text-muted);
  }
</style>
