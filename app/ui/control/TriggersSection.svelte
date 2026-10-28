<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import { NETWORK_TEXT, type NetworkMode } from "./model";

  // What starts work without you: the network state, scheduled jobs, context compaction and webhooks.
  type Job = { enabled: boolean };
  // Webhooks are not stored yet, so the list is empty until they are.
  const webhooks: { name: string; url: string }[] = [];

  let mode = $state<NetworkMode | null>(null);
  let jobs = $state<Job[]>([]);
  let error = $state<string | null>(null);
  const on = $derived(jobs.filter((job) => job.enabled).length);

  async function load(): Promise<void> {
    try {
      mode = (
        await invoke<{ mode: NetworkMode }>("sidecar_call", {
          method: "network",
        })
      ).mode;
      jobs = (await invoke<{ jobs: Job[] }>("sidecar_call", { method: "jobs" }))
        .jobs;
    } catch (cause) {
      error = String(cause);
    }
  }

  onMount(() => void load());
</script>

<section class="control-section" aria-labelledby="control-triggers">
  <h3 id="control-triggers">Triggers</h3>
  <p class="hint">What can start work on its own, without you asking.</p>
  <dl class="facts">
    <dt>Network</dt>
    <dd>{mode ? `${mode}: ${NETWORK_TEXT[mode]}` : "Checking…"}</dd>
    <dt>Scheduled jobs</dt>
    <dd>{jobs.length} set, {on} on</dd>
    <dt>Context compaction</dt>
    <dd>Not set up: the assistant does not shorten its context yet.</dd>
  </dl>
  <h4>Webhooks</h4>
  {#if webhooks.length === 0}
    <p class="muted">None. Webhooks are not set up in this build.</p>
  {:else}
    <ul>
      {#each webhooks as hook (hook.url)}
        <li>{hook.name} <span class="muted">{hook.url}</span></li>
      {/each}
    </ul>
  {/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>

<style>
  .facts {
    display: grid;
    grid-template-columns: max-content 1fr;
    gap: var(--space-1) var(--space-3);
    margin: 0;
  }

  .facts dt {
    color: var(--color-text-muted);
  }

  .facts dd {
    margin: 0;
  }

  h4 {
    margin: var(--space-3) 0 var(--space-1);
    font-size: var(--font-size-sm);
  }

  ul {
    margin: 0;
    padding-left: var(--space-4);
  }
</style>
