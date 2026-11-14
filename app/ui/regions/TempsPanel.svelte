<!-- Short-lived helper jobs (temps): a box to start one, then each prompt, its status and its result. At most four run at once. -->
<script lang="ts">
  import Loading from "../controls/Loading.svelte";
  import { onMount } from "svelte";
  import { every } from "../poll.ts";
  import { flagOn } from "../flags.svelte.ts";
  import { invoke } from "@tauri-apps/api/core";

  type Temp = { id: number; prompt: string; status: string; result: string };

  let temps = $state<Temp[]>([]);
  let failed = $state(false);
  // False until the first answer (or failure), so an empty list is not shown while it is still loading.
  let loaded = $state(false);

  // Read again every few seconds while this tab is open, so it does not go stale.
  async function load(): Promise<void> {
    try {
      temps = (
        await invoke<{ helpers: Temp[] }>("sidecar_call", { method: "helpers" })
      ).helpers;
      failed = false;
      loaded = true;
    } catch (cause) {
      failed = true;
      loaded = true;
      console.error("Could not read the temps", cause);
    }
  }
  // A temp is one request to the model, with no folder and no tools. Once started it runs to its end: it cannot be stopped.
  let objective = $state("");
  let starting = $state(false);
  let startError = $state<string | null>(null);
  async function start(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    starting = true;
    startError = null;
    try {
      temps = (
        await invoke<{ helpers: Temp[] }>("sidecar_call", {
          method: "start_helper",
          params: { prompt: objective.trim() },
        })
      ).helpers;
      objective = "";
    } catch (cause) {
      startError = String(cause);
    } finally {
      starting = false;
    }
  }
  onMount(() => {
    void load();
    return flagOn("panelRefresh") ? every(load, 5000) : undefined;
  });
</script>

<section class="temps" aria-label="Temps">
  <form class="start" aria-label="Start a temp" onsubmit={start}>
    <textarea
      rows="2"
      aria-label="What the temp should do"
      placeholder="One job for a temp, in a sentence or two"
      bind:value={objective}></textarea>
    <button type="submit" disabled={!objective.trim() || starting}
      >{starting ? "Starting…" : "Start temp"}</button
    >
    <p class="muted">
      A temp is one request to your model. It uses tokens, has no folder and no
      tools, and runs to its end.
    </p>
    {#if startError}<p class="error" role="alert">{startError}</p>{/if}
  </form>
  {#if !loaded}
    <Loading what="the temps" />
  {:else if failed}
    <p class="muted">Could not read the temps.</p>
  {:else if temps.length === 0}
    <p class="muted">No temps yet.</p>
  {:else}
    <ul>
      {#each temps as temp (temp.id)}
        <li>
          <span class="status {temp.status}">{temp.status}</span>
          <span class="prompt">{temp.prompt}</span>
          {#if temp.result}<small>{temp.result}</small>{/if}
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .temps {
    font-family: var(--font-ui);
    font-size: var(--font-size-xs);
    color: var(--color-md-text);
    overflow-y: auto;
  }

  .start {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    margin-bottom: var(--space-2);
  }

  .start textarea,
  .start button {
    padding: var(--space-1) var(--space-2);
    color: var(--color-md-text);
    font: inherit;
    background: var(--color-md-surface);
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
  }

  .start button {
    align-self: flex-start;
    min-height: var(--layout-control-h);
    cursor: pointer;
  }

  .start button:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .error {
    margin: 0;
    color: var(--color-danger);
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

  .status {
    color: var(--color-md-accent);
  }

  .status.failed {
    color: var(--color-md-text);
  }

  .status.done {
    color: var(--color-md-text-subtle);
  }

  .prompt {
    color: var(--color-md-text);
  }

  li small {
    flex-basis: 100%;
    color: var(--color-md-text-muted);
  }

  .muted {
    color: var(--color-md-text-muted);
  }
</style>
