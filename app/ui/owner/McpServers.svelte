<script lang="ts">
  // MCP servers for one added agent: the servers in its own folder's .mcp.json. Adding one here
  // turns it on for this agent only; its program reads the file at its next start.
  import Button from "../controls/Button.svelte";
  import { invoke } from "@tauri-apps/api/core";

  type Server = { name: string; kind: string; command: string; env: string };
  let { agent, name }: { agent: string; name: string } = $props();
  let servers = $state<Server[]>([]);
  let loaded = $state(false);
  let busy = $state(false);
  let error = $state<string | null>(null);
  let note = $state<string | null>(null);
  let newName = $state("");
  let line = $state("");

  async function call(
    method: string,
    params: Record<string, string>,
  ): Promise<void> {
    busy = true;
    error = null;
    try {
      const answer = await invoke<{ servers: Server[]; restart?: boolean }>(
        "sidecar_call",
        { method, params: { agent, ...params } },
      );
      servers = answer.servers;
      if (answer.restart)
        note = `Saved. ${name} uses the change from its next start.`;
    } catch (cause) {
      error = String(cause).replace(/^Error: /, "");
    } finally {
      busy = false;
      loaded = true;
    }
  }
  $effect(() => {
    void agent;
    note = null;
    void call("mcp_servers", {});
  });

  async function add(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    await call("mcp_add", { name: newName.trim(), line: line.trim() });
    if (!error) newName = line = "";
  }
</script>

<section class="mcp" aria-label="MCP servers of {name}">
  {#if !loaded}
    <p class="muted">Checking…</p>
  {:else if servers.length === 0}
    <p class="muted">No MCP servers in this agent's folder yet.</p>
  {:else}
    <ul aria-label="Servers">
      {#each servers as server (server.name)}
        <li>
          <strong>{server.name}</strong>
          <span class="mono">{server.command}</span>
          {#if server.env}<small>env: {server.env}</small>{/if}
          <button
            type="button"
            disabled={busy}
            onclick={() => call("mcp_remove", { name: server.name })}
            aria-label="Remove {server.name}">Remove</button
          >
        </li>
      {/each}
    </ul>
  {/if}
  <form onsubmit={add} aria-label="Add an MCP server">
    <input
      aria-label="Server name"
      placeholder="name"
      maxlength="48"
      bind:value={newName}
    />
    <input
      aria-label="Command or https address"
      placeholder="npx -y some-mcp-server  or  https://…"
      bind:value={line}
    />
    <Button type="submit" disabled={busy || !newName.trim() || !line.trim()}
      >Add</Button
    >
  </form>
  <p class="muted">
    Keys are not taken here: give a server its key the way its own docs say.
  </p>
  {#if note}<p class="muted" role="status">{note}</p>{/if}
  {#if error}<p class="muted" role="alert">{error}</p>{/if}
</section>

<style>
  .mcp {
    display: grid;
    gap: var(--space-2);
  }
  ul {
    display: grid;
    gap: var(--space-1);
    margin: 0;
    padding: 0;
    list-style: none;
  }
  li {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: baseline;
  }
  .mono {
    font-family: var(--font-mono);
    overflow-wrap: anywhere;
    flex: 1 1 12rem;
  }
  form {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }
  form input {
    flex: 1 1 10rem;
    min-width: 0;
    font: inherit;
  }
  p {
    margin: 0;
  }
</style>
