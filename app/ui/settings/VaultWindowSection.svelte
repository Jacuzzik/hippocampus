<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import Button from "../controls/Button.svelte";

  // 7.07: another vault in its own window, with its own agents, inboxes and memory. It is a second copy of the app,
  // so closing one window leaves the other open.
  let folder = $state("");
  let done = $state("");
  let error = $state("");
  let busy = $state(false);

  async function open(): Promise<void> {
    busy = true;
    error = done = "";
    try {
      const name = await invoke<string>("open_vault_window", {
        vault: folder.trim(),
      });
      done = `${name} is opening in a new window.`;
      folder = "";
    } catch (cause) {
      error = String(cause);
    } finally {
      busy = false;
    }
  }
</script>

<section class="control-section" aria-labelledby="windows-title">
  <h3 id="windows-title">Another vault in a new window</h3>
  <p class="hint">
    The new window has its own vault folder, agents, inboxes and memory. Each
    vault can be open in one window at a time.
  </p>
  <form
    class="row"
    onsubmit={(e) => {
      e.preventDefault();
      void open();
    }}
  >
    <input
      aria-label="Vault folder for the new window"
      placeholder="/path/to/another/vault"
      bind:value={folder}
    />
    <Button type="submit" disabled={busy || !folder.trim()}
      >Open in a new window</Button
    >
  </form>
  {#if done}<p role="status">{done}</p>{/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>

<style>
  .row {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    flex-wrap: wrap;
  }
  input {
    min-width: 0;
    flex: 1 1 240px;
  }
</style>
