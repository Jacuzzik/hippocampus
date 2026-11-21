<script lang="ts">
  import Button from "../controls/Button.svelte";
  import { invoke } from "@tauri-apps/api/core";

  // A password link to one note (14.04). Made on the user's account; the password is checked on the
  // server, so share it separately from the link.
  let { path, onclose }: { path: string; onclose: () => void } = $props();

  let password = $state("");
  let minutes = $state(60);
  let busy = $state(false);
  let error = $state<string | null>(null);
  let link = $state<{ url: string; expires_at?: string } | null>(null);
  let copied = $state(false);

  async function make(): Promise<void> {
    busy = true;
    error = null;
    try {
      link = await invoke("sidecar_call", {
        method: "share",
        params: { path, password, minutes },
      });
    } catch (cause) {
      error = String(cause);
    } finally {
      busy = false;
    }
  }

  async function copy(): Promise<void> {
    if (!link) return;
    try {
      await navigator.clipboard.writeText(link.url);
      copied = true;
    } catch {
      copied = false;
    }
  }
</script>

<section class="share" aria-label="Share this note">
  {#if link}
    <p>Link made. Send the password separately.</p>
    <input readonly aria-label="Share link" value={link.url} />
    <div class="row">
      <Button onclick={copy}>{copied ? "Copied" : "Copy link"}</Button>
      <button type="button" onclick={onclose}>Done</button>
    </div>
  {:else}
    <label
      >Password (8 or more characters)
      <input
        type="password"
        autocomplete="new-password"
        aria-label="Link password"
        bind:value={password}
      /></label
    >
    <label
      >Lasts
      <select aria-label="Link lasts" bind:value={minutes}>
        <option value={60}>1 hour</option>
        <option value={360}>6 hours</option>
        <option value={1440}>24 hours</option>
      </select></label
    >
    <div class="row">
      <Button disabled={busy || password.length < 8} onclick={make}
        >Make link</Button
      >
      <button type="button" onclick={onclose}>Cancel</button>
    </div>
  {/if}
  {#if error}<p class="muted" role="alert">{error}</p>{/if}
</section>

<style>
  .share {
    display: grid;
    gap: var(--space-2);
    padding: var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
  }
  label {
    display: grid;
    gap: var(--space-1);
  }
  .row {
    display: flex;
    gap: var(--space-2);
  }
</style>
