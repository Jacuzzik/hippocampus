<script lang="ts">
  import { onMount } from "svelte";
  import Button from "../controls/Button.svelte";
  import Toggle from "../controls/Toggle.svelte";
  import { call } from "./call";

  // G.04: off until turned on. A check is one request to GitHub's public releases page; nothing else is sent.
  type Found = {
    latest: string;
    newer: boolean;
    notes: string;
    text: string;
    url?: string;
    checked?: string;
  };
  type State = {
    on: boolean;
    current: string;
    last: Found | null;
    page: string;
  };
  let view = $state<State | null>(null);
  let error = $state("");
  let busy = $state(false);

  async function run(method: string, params = {}): Promise<void> {
    busy = true;
    error = "";
    try {
      view = await call<State>(method, params);
    } catch (cause) {
      error = String(cause);
    } finally {
      busy = false;
    }
  }
  onMount(() => void run("update_state"));
</script>

<section class="control-section" aria-labelledby="updates-title">
  <h3 id="updates-title">Updates and what's new</h3>
  <p class="hint">
    Off until you turn it on. A check asks GitHub for the newest release of
    Hippocampus and sends nothing else. Nothing is downloaded by itself.
  </p>
  {#if view}
    <div class="row">
      <Toggle
        ariaLabel="Check for updates"
        checked={view.on}
        label={view.on ? "On" : "Off"}
        onchange={(on) => void run("update_set", { on })}
      />
      <span class="muted">You have version {view.current}.</span>
      <Button
        disabled={!view.on || busy}
        onclick={() => void run("update_check")}>Check now</Button
      >
    </div>
    {#if view.last}
      <p role="status">
        {view.last.text}
        {#if view.last.newer && view.last.url}
          <a href={view.last.url} target="_blank" rel="noreferrer">Get it</a>
        {/if}
      </p>
      {#if view.last.notes}
        <h4>What's new in {view.last.latest}</h4>
        <pre class="notes">{view.last.notes}</pre>
      {/if}
    {/if}
  {/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>

<style>
  .row {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    flex-wrap: wrap;
  }
  .notes {
    white-space: pre-wrap;
    max-height: 240px;
    overflow: auto;
    font-size: var(--font-size-sm, 0.85rem);
  }
</style>
