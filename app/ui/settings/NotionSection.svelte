<script lang="ts">
  import { onMount } from "svelte";
  import Button from "../controls/Button.svelte";
  import { call } from "./call";

  // Notion (D.07): read pages and databases into vault notes. The app never changes anything in Notion.
  type Row = { id: string; kind: string; title: string; edited: string };
  let connected = $state(false);
  let token = $state("");
  let query = $state("");
  let results = $state<Row[]>([]);
  let done = $state("");
  let error = $state("");
  let busy = $state(false);

  async function act(fn: () => Promise<void>): Promise<void> {
    busy = true;
    error = "";
    try {
      await fn();
    } catch (cause) {
      error = String(cause);
    } finally {
      busy = false;
    }
  }
  const setView = (r: { connected: boolean }): void => {
    connected = r.connected;
  };
  onMount(() => void act(async () => setView(await call("notion_state"))));
</script>

<section class="control-section" aria-labelledby="notion-title">
  <h3 id="notion-title">Notion</h3>
  <p class="hint">
    Make an internal integration at notion.so/my-integrations, share the pages
    it may read with it (a page's ⋯ menu, Connections), and paste its secret.
    Pages are read into notes in the vault's Notion folder. Nothing in Notion is
    changed.
  </p>
  {#if !connected}
    <form
      class="row"
      onsubmit={(e) => {
        e.preventDefault();
        void act(async () => {
          setView(await call("notion_connect", { token }));
          token = "";
        });
      }}
    >
      <input
        aria-label="Notion secret"
        type="password"
        placeholder="ntn_…"
        bind:value={token}
      />
      <Button type="submit" variant="primary" disabled={busy || !token.trim()}
        >Connect</Button
      >
    </form>
  {:else}
    <form
      class="row"
      onsubmit={(e) => {
        e.preventDefault();
        void act(async () => {
          results = (await call<{ results: Row[] }>("notion_search", { query }))
            .results;
        });
      }}
    >
      <input
        aria-label="Search Notion"
        placeholder="Search pages"
        bind:value={query}
      />
      <Button type="submit" disabled={busy}>Search</Button>
      <Button
        variant="ghost"
        onclick={() =>
          void act(async () => setView(await call("notion_disconnect")))}
        >Disconnect</Button
      >
    </form>
    {#if results.length}
      <ul aria-label="Notion pages">
        {#each results as row (row.id)}
          <li>
            {row.title} <span class="muted">{row.kind}, {row.edited}</span>
            <Button
              size="sm"
              disabled={busy}
              onclick={() =>
                void act(async () => {
                  const made = await call<{ path: string }>("notion_import", {
                    id: row.id,
                  });
                  done = `Saved to ${made.path}`;
                })}>Read into a note</Button
            >
          </li>
        {/each}
      </ul>
    {/if}
    {#if done}<p role="status">{done}</p>{/if}
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
  input {
    min-width: 0;
    flex: 1 1 200px;
  }
  li {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    flex-wrap: wrap;
  }
</style>
