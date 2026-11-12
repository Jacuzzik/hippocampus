<!-- Right-click menu for a graph note, styled as the agent card's menu (AgentBar). Edit opens the note's sidebar. -->
<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import type { GraphData } from "./model.ts";

  export type MenuTarget = { x: number; y: number; id: string };
  type Scope = "note" | "hub" | "group";
  type View = "menu" | "colour" | "delete";

  let {
    menu,
    data,
    onclose,
    onedit,
  }: {
    menu: MenuTarget | null;
    data: GraphData;
    onclose: () => void;
    onedit: (id: string) => void;
  } = $props();

  // The status tags that set a note's colour, and the accent for no tag. Mirrors STATUS_COLOURS in BrainGraph.
  const COLOURS: [string, string][] = [
    ["important", "Red"],
    ["done", "Green"],
    ["pending", "Yellow"],
    ["action", "Orange"],
    ["agent", "White"],
    ["", "Accent (clear)"],
  ];
  // Hub notes at the vault root, as vault_tools.HUB_NOTES lists them, in lower case (file names match without case).
  const HUBS = new Set(
    [
      "WELCOME",
      "MAIN",
      "Projects",
      "Summaries",
      "Agent Lists",
      "Contacts",
      "Socials",
      "About User",
      "Test Hub",
    ].map((name) => name.toLowerCase()),
  );

  let view = $state<View>("menu");
  let scope = $state<Scope>("note");
  let error = $state<string | null>(null);
  let busy = $state(false);

  const isHub = (id: string) =>
    !id.includes("/") && HUBS.has(id.replace(/\.md$/i, "").toLowerCase());
  // MAIN is never deleted, and the backend refuses it too (vault_tools.main_guard).
  const isMain = (id: string) =>
    !id.includes("/") && id.replace(/\.md$/i, "").toLowerCase() === "main";
  // Notes MAIN links to are protected too: the backend refuses them (vault_tools.main_guard).
  const fromMain = (id: string) =>
    data.edges.some(([a, b]) => b === id && isMain(a));
  const title = (id: string) =>
    data.nodes.find((n) => n.id === id)?.title ?? id;
  // A group is its hub plus the notes the hub links to (one level, as the backend counts it).
  const groupOf = (id: string) => [
    id,
    ...new Set(data.edges.filter(([a]) => a === id).map(([, b]) => b)),
  ];

  // A new right-click starts again at the menu.
  $effect(() => {
    if (menu) {
      view = "menu";
      error = null;
    }
  });

  async function call(
    method: string,
    params: Record<string, unknown>,
  ): Promise<void> {
    busy = true;
    error = null;
    try {
      await invoke("sidecar_call", { method, params });
      window.dispatchEvent(new Event("graph-changed"));
      onclose();
    } catch (cause) {
      error = String(cause);
    } finally {
      busy = false;
    }
  }

  function startColour(next: Scope): void {
    scope = next;
    view = "colour";
  }

  function startDelete(next: Scope): void {
    scope = next;
    view = "delete";
  }
</script>

{#if menu}
  {@const open = menu}
  <div
    class="menu-scrim"
    role="presentation"
    onmousedown={onclose}
    oncontextmenu={(e) => {
      e.preventDefault();
      onclose();
    }}
  ></div>
  <div
    class="card-menu"
    role="menu"
    aria-label="Note actions"
    style="left: {open.x}px; top: {open.y}px"
  >
    {#if view === "menu"}
      {#if isHub(open.id)}
        {#if !isMain(open.id)}
          <button
            type="button"
            role="menuitem"
            onclick={() => startDelete("group")}>Delete whole group</button
          >
        {/if}
        <button
          type="button"
          role="menuitem"
          onclick={() => startColour("group")}>Colour whole group</button
        >
        {#if !isMain(open.id)}
          <button
            type="button"
            role="menuitem"
            onclick={() => startDelete("hub")}
            >Delete hub only and unlink</button
          >
        {/if}
        <button type="button" role="menuitem" onclick={() => startColour("hub")}
          >Colour hub only</button
        >
      {:else}
        <button
          type="button"
          role="menuitem"
          onclick={() => {
            onedit(open.id);
            onclose();
          }}>Edit</button
        >
        <button
          type="button"
          role="menuitem"
          onclick={() => startColour("note")}>Change colour</button
        >
        {#if !isMain(open.id) && !fromMain(open.id)}
          <button
            type="button"
            role="menuitem"
            class="danger"
            onclick={() => startDelete("note")}>Delete</button
          >
        {/if}
      {/if}
    {:else if view === "colour"}
      <p class="heading">
        Colour {scope === "group"
          ? "whole group"
          : scope === "hub"
            ? "hub only"
            : title(open.id)}
      </p>
      {#each COLOURS as [tag, label] (tag)}
        <button
          type="button"
          role="menuitem"
          disabled={busy}
          onclick={() =>
            call("note_colour", { path: open.id, scope, status: tag })}
          >{label}</button
        >
      {/each}
      <button type="button" class="back" onclick={() => (view = "menu")}
        >Back</button
      >
    {:else}
      {@const names = scope === "group" ? groupOf(open.id) : [open.id]}
      <p class="heading">
        Delete {names.length}
        {names.length === 1 ? "note" : "notes"}?
      </p>
      <p class="muted">
        {scope === "hub"
          ? "Only the hub is removed. The notes it links to stay, unlinked."
          : "These files are removed from the vault."} This cannot be undone.
      </p>
      <ul>
        {#each names as id (id)}<li>{title(id)}</li>{/each}
      </ul>
      <button type="button" class="back" onclick={() => (view = "menu")}
        >Cancel</button
      >
      <button
        type="button"
        role="menuitem"
        class="danger"
        disabled={busy}
        onclick={() => call("note_delete", { path: open.id, scope })}
        >Delete</button
      >
    {/if}
    {#if error}<p class="error" role="alert">{error}</p>{/if}
  </div>
{/if}

<style>
  /* The same look as the agent card's menu in AgentBar.svelte. */
  .menu-scrim {
    position: fixed;
    inset: 0;
    z-index: 20;
  }

  .card-menu {
    position: fixed;
    z-index: 21;
    display: grid;
    min-width: 170px;
    max-width: 280px;
    padding: var(--space-1);
    background: var(--color-bg-1);
    color: var(--color-text);
    border: 1px solid var(--color-border);
    border-radius: 0;
  }

  .card-menu button {
    padding: var(--space-2);
    border: none;
    background: none;
    color: inherit;
    text-align: left;
    font-size: var(--font-size-xs);
    cursor: pointer;
  }

  .card-menu button:hover {
    background: var(--color-surface);
  }

  .card-menu button:disabled {
    opacity: 0.5;
    cursor: default;
  }

  /* Delete sits under a divider, in red, as in the agent card's menu. */
  .card-menu .danger {
    margin-top: 4px;
    padding-top: var(--space-2);
    border-top: 1px solid var(--color-border);
    color: var(--color-danger);
  }

  .card-menu .back {
    color: var(--color-text-muted);
  }

  .heading {
    margin: 0;
    padding: var(--space-2);
    font-size: var(--font-size-xs);
    color: var(--color-text);
  }

  .muted,
  .error {
    margin: 0;
    padding: 0 var(--space-2) var(--space-2);
    font-size: var(--font-size-xs);
  }

  .muted {
    color: var(--color-text-muted);
  }

  .error {
    color: var(--color-danger);
  }

  ul {
    margin: 0;
    padding: 0 var(--space-2) var(--space-2) var(--space-4);
    max-height: 30vh;
    overflow-y: auto;
    font-size: var(--font-size-xs);
  }
</style>
