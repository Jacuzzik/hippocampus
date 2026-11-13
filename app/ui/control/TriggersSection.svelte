<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import { NETWORK_TEXT, type NetworkMode } from "./model";
  import StatusCard from "../controls/StatusCard.svelte";
  import Loading from "../controls/Loading.svelte";

  // What starts work without you: the network state, scheduled jobs, context compaction and webhooks.
  type Job = { enabled: boolean };
  type Webhook = { id: string; name: string; kind: string };

  let mode = $state<NetworkMode | null>(null);
  let jobs = $state<Job[]>([]);
  let webhooks = $state<Webhook[]>([]);
  let error = $state<string | null>(null);
  // False until the first answer (or failure).
  let loaded = $state(false);
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
      webhooks = (
        await invoke<{ webhooks: Webhook[] }>("sidecar_call", {
          method: "webhooks",
        })
      ).webhooks;
    } catch (cause) {
      error = String(cause);
    } finally {
      loaded = true;
    }
  }

  onMount(() => void load());
</script>

<section class="control-section" aria-labelledby="control-triggers">
  <h3 id="control-triggers">Triggers</h3>
  <p class="hint">What can start work on its own, without you asking.</p>
  {#if !loaded}
    <Loading what="the triggers" />
  {:else}
    <dl class="facts">
      <dt>Network</dt>
      <dd>{mode ? `${mode}: ${NETWORK_TEXT[mode]}` : "Checking…"}</dd>
      <dt>Scheduled jobs</dt>
      <dd>{jobs.length} set, {on} on</dd>
    </dl>
    <StatusCard
      name="Context compaction"
      what="Shortens a long chat on its own, so the assistant keeps working without losing the thread."
      status="Planned"
      reason="The assistant does not shorten its context yet."
    />
    <h4>Webhooks</h4>
    {#if webhooks.length === 0}
      <p class="muted">None saved yet.</p>
    {:else}
      <ul>
        {#each webhooks as hook (hook.id)}
          <li>{hook.name} <span class="muted">runs {hook.kind}</span></li>
        {/each}
      </ul>
    {/if}
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
