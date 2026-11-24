<script lang="ts">
  import { onMount } from "svelte";
  import Button from "../controls/Button.svelte";
  import { call } from "./call";

  // 7.09: notes found by what they mean, with a local embedding model served by Ollama. No note leaves this machine.
  type State = { model: string; notes: number; built: boolean; read?: number };
  let view = $state<State | null>(null);
  let query = $state("");
  let results = $state<{ path: string; score: number }[]>([]);
  let error = $state("");
  let busy = $state(false);

  async function act(fn: () => Promise<void>): Promise<void> {
    busy = true;
    error = "";
    try {
      await fn();
    } catch (cause) {
      error = String(cause);
    } finally {
      busy = false;
    }
  }
  onMount(
    () =>
      void act(async () => {
        view = await call<State>("semantic_state");
      }),
  );
</script>

<section class="control-section" aria-labelledby="meaning-title">
  <h3 id="meaning-title">Search by meaning</h3>
  <p class="hint">
    Finds notes by what they are about, not only their words. It uses a local
    embedding model through Ollama ({view?.model ?? "nomic-embed-text"}), so no
    note leaves this computer. Install Ollama, run
    <code>ollama pull {view?.model ?? "nomic-embed-text"}</code>, then build the
    index. Building again reads only changed notes.
  </p>
  <div class="row">
    <Button
      disabled={busy}
      onclick={() =>
        void act(async () => {
          view = await call<State>("semantic_build");
        })}>{view?.built ? "Update the index" : "Build the index"}</Button
    >
    {#if view}<span class="muted" role="status"
        >{view.notes} notes in the index.</span
      >{/if}
  </div>
  <form
    class="row"
    onsubmit={(e) => {
      e.preventDefault();
      void act(async () => {
        results = (
          await call<{ results: typeof results }>("semantic_search", { query })
        ).results;
      });
    }}
  >
    <input
      aria-label="Search by meaning"
      placeholder="What are you looking for?"
      bind:value={query}
    />
    <Button type="submit" disabled={busy || !query.trim() || !view?.notes}
      >Search</Button
    >
  </form>
  {#if results.length}
    <ol aria-label="Closest notes">
      {#each results as row (row.path)}
        <li>{row.path} <span class="muted">{row.score}</span></li>
      {/each}
    </ol>
  {/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>

<style>
  .row {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    flex-wrap: wrap;
    margin-top: var(--space-2);
  }
  input {
    min-width: 0;
    flex: 1 1 200px;
  }
</style>
