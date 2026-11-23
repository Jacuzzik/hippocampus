<script lang="ts">
  import Button from "../controls/Button.svelte";
  import { invoke } from "@tauri-apps/api/core";

  // Note history (N.21): the earlier versions kept before each editing session, the last 20.
  // Show reads one; Restore puts it back, and the text it replaces is kept first, so it can be undone.
  type Version = { id: string; time: number; chars: number; first: string };
  let {
    path,
    onclose,
    onrestored,
  }: {
    path: string;
    onclose: () => void;
    onrestored: (text: string) => void;
  } = $props();

  let versions = $state<Version[] | null>(null);
  let preview = $state<{ id: string; text: string } | null>(null);
  let busy = $state(false);
  let error = $state<string | null>(null);

  async function load(): Promise<void> {
    error = null;
    try {
      const answer = await invoke<{ versions: Version[] }>("sidecar_call", {
        method: "note_history",
        params: { path },
      });
      versions = answer.versions;
    } catch (cause) {
      error = String(cause);
    }
  }

  async function show(id: string): Promise<void> {
    if (preview?.id === id) {
      preview = null;
      return;
    }
    error = null;
    try {
      const answer = await invoke<{ text: string }>("sidecar_call", {
        method: "note_version",
        params: { path, version: id },
      });
      preview = { id, text: answer.text };
    } catch (cause) {
      error = String(cause);
    }
  }

  async function restore(id: string): Promise<void> {
    busy = true;
    error = null;
    try {
      const answer = await invoke<{ text: string }>("sidecar_call", {
        method: "note_restore",
        params: { path, version: id },
      });
      preview = null;
      onrestored(answer.text);
      await load();
    } catch (cause) {
      error = String(cause);
    } finally {
      busy = false;
    }
  }

  const when = (ms: number): string =>
    new Date(ms).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    });

  $effect(() => {
    void path;
    preview = null;
    void load();
  });
</script>

<section class="history" aria-label="Note history">
  <div class="row head">
    <strong>Earlier versions</strong>
    <button type="button" onclick={onclose}>Done</button>
  </div>
  {#if versions === null && !error}
    <p class="muted">Loading…</p>
  {:else if versions && versions.length === 0}
    <p class="muted">
      No earlier versions yet. One is kept each time you start editing this note,
      the last 20.
    </p>
  {:else if versions}
    <ul aria-label="Versions">
      {#each versions as version (version.id)}
        <li>
          <div class="what">
            <span>{when(version.time)}</span>
            <span class="muted">{version.chars} characters · {version.first}</span>
          </div>
          <div class="row">
            <button
              type="button"
              aria-pressed={preview?.id === version.id}
              onclick={() => show(version.id)}>Show</button
            >
            <Button disabled={busy} onclick={() => restore(version.id)}
              >Restore</Button
            >
          </div>
          {#if preview?.id === version.id}
            <pre aria-label="Version text">{preview.text}</pre>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}
  {#if error}<p class="muted" role="alert">{error}</p>{/if}
</section>

<style>
  .history {
    display: grid;
    gap: var(--space-2);
    padding: var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
  }
  .row {
    display: flex;
    gap: var(--space-2);
    align-items: center;
  }
  .head {
    justify-content: space-between;
  }
  ul {
    display: grid;
    gap: var(--space-2);
    margin: 0;
    padding: 0;
    list-style: none;
  }
  li {
    display: grid;
    gap: var(--space-1);
  }
  .what {
    display: grid;
    min-width: 0;
  }
  .what .muted {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  pre {
    max-height: 16rem;
    overflow: auto;
    margin: 0;
    padding: var(--space-2);
    white-space: pre-wrap;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
  }
</style>
