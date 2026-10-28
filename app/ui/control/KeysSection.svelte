<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import { keyStatus } from "./model";

  // Saved keys are kept in the OS keychain. A saved key takes effect on the next request.
  type KeyRow = {
    provider: string;
    label: string;
    saved: boolean;
    hint: string | null;
  };

  let keys = $state<KeyRow[]>([]);
  let drafts = $state<Record<string, string>>({});
  let error = $state<string | null>(null);

  async function load(): Promise<void> {
    try {
      keys = (
        await invoke<{ keys: KeyRow[] }>("sidecar_call", { method: "keys" })
      ).keys;
    } catch (cause) {
      error = String(cause);
    }
  }

  async function save(row: KeyRow): Promise<void> {
    error = null;
    try {
      keys = (
        await invoke<{ keys: KeyRow[] }>("sidecar_call", {
          method: "save_key",
          params: { provider: row.provider, key: drafts[row.provider] ?? "" },
        })
      ).keys;
      drafts[row.provider] = "";
    } catch (cause) {
      error = String(cause);
    }
  }

  async function clear(row: KeyRow): Promise<void> {
    error = null;
    try {
      keys = (
        await invoke<{ keys: KeyRow[] }>("sidecar_call", {
          method: "clear_key",
          params: { provider: row.provider },
        })
      ).keys;
    } catch (cause) {
      error = String(cause);
    }
  }

  onMount(() => void load());
</script>

<section class="control-section" aria-labelledby="control-keys">
  <h3 id="control-keys">Keys and secrets</h3>
  <p class="hint">
    Saved keys take effect at once, with no restart. A key is never shown in
    full: only its last four characters.
  </p>
  <ul aria-label="Saved keys">
    {#each keys as row (row.provider)}
      <li>
        <div class="row">
          <strong>{row.label}</strong>
          <span class="muted">{keyStatus(row.saved, row.hint)}</span>
        </div>
        <div class="row">
          <input
            type="password"
            aria-label={`New ${row.label} key`}
            autocomplete="off"
            bind:value={drafts[row.provider]}
          />
          <button type="button" class="primary" onclick={() => save(row)}>
            {row.saved ? "Replace" : "Save"}
          </button>
          {#if row.saved}<button type="button" onclick={() => clear(row)}
              >Remove</button
            >{/if}
        </div>
      </li>
    {/each}
  </ul>
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>
