<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { onDestroy, onMount } from "svelte";

  // Short-lived helpers: one prompt, run once, result reported back. Four run at once, at most.
  type Helper = {
    id: number;
    prompt: string;
    status: "running" | "done" | "failed";
    result: string;
  };

  let helpers = $state<Helper[]>([]);
  let limit = $state(4);
  let prompt = $state("");
  let error = $state<string | null>(null);
  let timer: ReturnType<typeof setInterval> | undefined;
  const running = $derived(
    helpers.filter((h) => h.status === "running").length,
  );

  async function load(): Promise<void> {
    try {
      const state = await invoke<{ helpers: Helper[]; limit: number }>(
        "sidecar_call",
        {
          method: "helpers",
        },
      );
      helpers = state.helpers;
      limit = state.limit;
    } catch (cause) {
      error = String(cause);
    }
  }

  async function start(): Promise<void> {
    error = null;
    try {
      await invoke("sidecar_call", {
        method: "start_helper",
        params: { prompt },
      });
      prompt = "";
      await load();
    } catch (cause) {
      error = String(cause);
    }
  }

  onMount(() => {
    void load();
    timer = setInterval(load, 2000);
  });
  onDestroy(() => clearInterval(timer));
</script>

<section class="control-section" aria-labelledby="control-helpers">
  <h3 id="control-helpers">Helper jobs</h3>
  <p class="hint">
    {running} of {limit} running. A helper runs its prompt once and reports back.
  </p>
  <textarea rows="2" aria-label="Helper prompt" bind:value={prompt}></textarea>
  <div class="row">
    <button
      type="button"
      class="primary"
      disabled={!prompt.trim() || running >= limit}
      onclick={start}>Start helper</button
    >
    {#if running >= limit}<span class="muted"
        >All {limit} slots are in use.</span
      >{/if}
  </div>
  {#if helpers.length}
    <ul aria-label="Helpers">
      {#each helpers as helper (helper.id)}
        <li>
          <span class="badge">{helper.status}</span>
          {helper.prompt}
          {#if helper.result}<p class="muted">{helper.result}</p>{/if}
        </li>
      {/each}
    </ul>
  {/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>
