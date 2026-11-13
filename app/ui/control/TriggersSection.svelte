<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import { NETWORK_TEXT, type NetworkMode } from "./model";
  import StatusCard from "../controls/StatusCard.svelte";
  import Loading from "../controls/Loading.svelte";
  import { report } from "../notices.svelte.ts";

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

  // The only job a webhook can run today is the link check (core/jobs.py KINDS).
  const KINDS = [{ id: "link_check", label: "Link check" }];
  let newName = $state("");
  let newKind = $state(KINDS[0]?.id ?? "link_check");
  let confirming = $state<string | null>(null);

  async function add(): Promise<void> {
    const name = newName.trim();
    if (!name) return;
    try {
      webhooks = (
        await invoke<{ webhooks: Webhook[] }>("sidecar_call", {
          method: "save_webhook",
          params: { name, kind: newKind },
        })
      ).webhooks;
      newName = "";
    } catch (cause) {
      report("Could not save the webhook", cause);
    }
  }

  async function remove(id: string): Promise<void> {
    if (confirming !== id) {
      confirming = id;
      return;
    }
    confirming = null;
    try {
      webhooks = (
        await invoke<{ webhooks: Webhook[] }>("sidecar_call", {
          method: "delete_webhook",
          params: { id },
        })
      ).webhooks;
    } catch (cause) {
      report("Could not remove the webhook", cause);
    }
  }
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
          <li>
            {hook.name} <span class="muted">runs {hook.kind}</span>
            <button
              type="button"
              aria-label={confirming === hook.id
                ? `Confirm remove ${hook.name}`
                : `Remove ${hook.name}`}
              onclick={() => void remove(hook.id)}
              >{confirming === hook.id ? "Confirm remove" : "Remove"}</button
            >
          </li>
        {/each}
      </ul>
    {/if}
    <form
      class="add"
      onsubmit={(e) => {
        e.preventDefault();
        void add();
      }}
    >
      <label
        >Name <input type="text" bind:value={newName} maxlength="80" /></label
      >
      <label
        >Runs
        <select bind:value={newKind}>
          {#each KINDS as kind (kind.id)}
            <option value={kind.id}>{kind.label}</option>
          {/each}
        </select>
      </label>
      <button type="submit" disabled={!newName.trim()}>Add webhook</button>
    </form>
    <p class="muted">
      A webhook runs one local job after you approve it. Nothing listens on a
      network port, so no outside service can call it yet.
    </p>
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

  li {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .add {
    display: flex;
    flex-wrap: wrap;
    align-items: end;
    gap: var(--space-2);
    margin-top: var(--space-2);
  }

  .add label {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }
</style>
