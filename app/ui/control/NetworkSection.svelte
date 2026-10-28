<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import { NETWORK_MODES, NETWORK_TEXT, type NetworkMode } from "./model";

  // Which directions the app may reach outside this machine. Off is the default.
  let mode = $state<NetworkMode>("off");
  let error = $state<string | null>(null);

  async function load(): Promise<void> {
    try {
      const result = await invoke<{ mode: NetworkMode }>("sidecar_call", {
        method: "network",
      });
      mode = result.mode;
    } catch (cause) {
      error = String(cause);
    }
  }

  async function choose(next: NetworkMode): Promise<void> {
    error = null;
    try {
      const result = await invoke<{ mode: NetworkMode }>("sidecar_call", {
        method: "set_network",
        params: { mode: next },
      });
      mode = result.mode;
    } catch (cause) {
      error = String(cause);
      await load();
    }
  }

  onMount(() => void load());
</script>

<section class="control-section" aria-labelledby="control-network">
  <h3 id="control-network">Network</h3>
  <p class="hint">
    Where the app may send data. Model calls are the only outbound calls it
    makes today. Off blocks them all, and it is the default.
  </p>
  <div class="row" role="group" aria-label="Network mode">
    {#each NETWORK_MODES as option (option)}
      <button
        type="button"
        class="segment"
        aria-pressed={mode === option}
        onclick={() => choose(option)}
      >
        {option.charAt(0).toUpperCase() + option.slice(1)}
      </button>
    {/each}
  </div>
  <p class="hint">{NETWORK_TEXT[mode]}</p>
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>
