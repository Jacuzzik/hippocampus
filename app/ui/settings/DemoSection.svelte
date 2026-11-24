<script lang="ts">
  import { onMount } from "svelte";
  import Button from "../controls/Button.svelte";
  import { call } from "./call";

  // N.26: the sample vault lives in the app's own storage folder; opening it is a vault switch that can be undone.
  type State = { in_demo: boolean; notes: number; label: string };
  let view = $state<State | null>(null);
  let error = $state("");
  let busy = $state(false);

  async function run(method: string): Promise<void> {
    busy = true;
    error = "";
    try {
      view = await call<State>(method);
      if (method !== "demo_state") {
        window.dispatchEvent(new CustomEvent("graph-changed"));
      }
    } catch (cause) {
      error = String(cause);
    } finally {
      busy = false;
    }
  }
  onMount(() => void run("demo_state"));
</script>

<section class="control-section" aria-labelledby="demo-title">
  <h3 id="demo-title">Demo vault and tour</h3>
  <p class="hint">
    A small sample vault with linked notes, so you can see the graph before your
    own notes are in it. It is kept apart from your vault, and going back is one
    click.
  </p>
  {#if view}
    <p>
      {view.in_demo
        ? "The demo vault is open. Nothing in it is yours."
        : `The demo vault has ${view.notes} sample notes.`}
    </p>
    <div class="row">
      {#if view.in_demo}
        <Button disabled={busy} onclick={() => void run("demo_leave")}
          >Back to my vault</Button
        >
      {:else}
        <Button disabled={busy} onclick={() => void run("demo_open")}
          >Open the demo vault</Button
        >
      {/if}
      <Button
        onclick={() => window.dispatchEvent(new CustomEvent("start-tour"))}
        >Take the tour</Button
      >
    </div>
  {/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>

<style>
  .row {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
  }
</style>
