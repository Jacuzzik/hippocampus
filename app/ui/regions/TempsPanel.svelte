<!-- Short-lived helper jobs (temps), read only: each prompt, its status and its result. At most four run at once. -->
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
  onMount(() => {
    void load();
    return flagOn("panelRefresh") ? every(load, 5000) : undefined;
  });
</script>

<section class="temps" aria-label="Temps">
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
