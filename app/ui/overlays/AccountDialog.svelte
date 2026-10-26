<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { onMount, tick } from "svelte";

  // Setup and account, as in Munder Difflin's onboarding: open the brain folder, then sign in to
  // Claude with an API key kept in the OS keychain. Sign out forgets the key and needs a second press.
  let { onclose, onopened }: { onclose: () => void; onopened: () => void } =
    $props();

  let signedIn = $state<boolean | null>(null);
  let vault = $state("");
  let key = $state("");
  let error = $state<string | null>(null);
  let confirmSignOut = $state(false);
  let vaultInput: HTMLInputElement | null = $state(null);

  onMount(async () => {
    try {
      signedIn = (
        await invoke<{ claude: boolean }>("sidecar_call", { method: "account" })
      ).claude;
    } catch (cause) {
      error = String(cause);
    }
    await tick();
    vaultInput?.focus();
  });

  async function openBrain(e: SubmitEvent): Promise<void> {
    e.preventDefault();
    error = null;
    try {
      await invoke("sidecar_call", {
        method: "open",
        params: { vault: vault.trim() },
      });
      onopened();
      onclose();
    } catch (cause) {
      error = String(cause);
    }
  }

  async function signIn(e: SubmitEvent): Promise<void> {
    e.preventDefault();
    error = null;
    try {
      const result = await invoke<{ claude: boolean }>("sidecar_call", {
        method: "sign_in",
        params: { key: key.trim() },
      });
      signedIn = result.claude;
      key = "";
    } catch (cause) {
      error = String(cause);
    }
  }

  async function signOut(): Promise<void> {
    if (!confirmSignOut) {
      confirmSignOut = true;
      return;
    }
    confirmSignOut = false;
    error = null;
    try {
      signedIn = (
        await invoke<{ claude: boolean }>("sidecar_call", {
          method: "sign_out",
        })
      ).claude;
    } catch (cause) {
      error = String(cause);
    }
  }

  function onKey(e: KeyboardEvent): void {
    // Stops here so the graph's own Escape (which clears the selection) does not also run.
    if (e.key === "Escape") {
      e.stopPropagation();
      onclose();
    }
  }
</script>

<div class="scrim" role="presentation" onmousedown={onclose}>
  <div
    class="box"
    role="dialog"
    aria-modal="true"
    aria-label="Setup and account"
    tabindex="-1"
    onkeydown={onKey}
    onmousedown={(e) => e.stopPropagation()}
  >
    <h2>Setup and account</h2>

    <form class="section" onsubmit={openBrain}>
      <h3>Brain folder</h3>
      <p class="muted">The folder of Markdown notes Hippocampus shows.</p>
      <div class="row">
        <input
          bind:this={vaultInput}
          bind:value={vault}
          aria-label="Brain folder path"
          placeholder="/path/to/brain"
          autocomplete="off"
          required
        />
        <button type="submit" class="primary">Open brain</button>
      </div>
    </form>

    <div class="section">
      <h3>Claude</h3>
      {#if signedIn === null}
        <p class="muted">Checking sign-in…</p>
      {:else if signedIn}
        <p>Signed in to Claude. The assistant uses Claude first.</p>
        <button type="button" onclick={signOut}>
          {confirmSignOut ? "Press again to sign out" : "Sign out"}
        </button>
      {:else}
        <p class="muted">
          Not signed in. The assistant uses Ollama on this machine.
        </p>
        <form class="row" onsubmit={signIn}>
          <input
            bind:value={key}
            type="password"
            aria-label="Claude API key"
            placeholder="sk-ant-…"
            autocomplete="off"
            required
          />
          <button type="submit" class="primary">Sign in</button>
        </form>
      {/if}
    </div>

    {#if error}
      <p role="alert" class="error">{error}</p>
    {/if}
  </div>
</div>

<style>
  .scrim {
    position: fixed;
    inset: 0;
    z-index: 10;
    display: flex;
    justify-content: center;
    align-items: flex-start;
    padding-top: 12vh;
  }

  .box {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    width: min(560px, 90vw);
    padding: var(--space-3);
    background: var(--color-bg-1);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    color: var(--color-text);
  }

  h2 {
    margin: 0;
    font-size: var(--font-size-sm);
  }

  h3 {
    margin: 0;
    font-size: var(--font-size-sm);
  }

  p {
    margin: var(--space-1) 0;
  }

  .section {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .row {
    display: flex;
    gap: var(--space-2);
  }

  input {
    flex: 1;
    min-width: 0;
    font: inherit;
    color: var(--color-text);
    background: var(--color-bg-0);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    padding: var(--space-1) var(--space-2);
  }

  button {
    font: inherit;
    color: var(--color-text);
    background: var(--color-bg-0);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    padding: var(--space-1) var(--space-3);
    cursor: pointer;
  }

  button.primary {
    color: var(--color-accent-on);
    background: var(--color-accent);
    border-color: var(--color-accent);
  }

  .muted {
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }

  .error {
    color: var(--color-text);
  }
</style>
