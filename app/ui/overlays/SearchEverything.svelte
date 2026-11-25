<script lang="ts">
  // One search box for everything (N.01): notes, messages, tasks, calendar events and agents, from
  // one backend call. Picking a row opens it: a note in the graph, an agent's panel, the inbox or
  // tasks tab, or the dashboards for an event.
  import Dialog from "../controls/Dialog.svelte";
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";

  type Row = {
    id: string;
    group: string;
    label: string;
    hint: string;
    run: () => void;
  };
  type Found = {
    notes: { path: string; title: string; snippet: string }[];
    messages: {
      id: string;
      from: string;
      to: string;
      subject: string;
      snippet: string;
    }[];
    tasks: { id: string; title: string; status: string }[];
    events: { id: string; date: string; time: string; title: string }[];
    agents: { id: string; name: string }[];
  };
  let {
    onclose,
    onnote,
    onagent,
    ondashboards,
  }: {
    onclose: () => void;
    onnote: (path: string) => void;
    onagent: (id: string) => void;
    ondashboards: () => void;
  } = $props();

  let query = $state("");
  let rows = $state<Row[]>([]);
  let active = $state(0);
  let error = $state<string | null>(null);
  let searched = $state(false);
  let busy = $state(false);
  let input: HTMLInputElement | null = $state(null);
  let timer = 0;
  let asked = 0;
  const tab = (id: string) => () =>
    window.dispatchEvent(new CustomEvent("show-tab", { detail: id }));

  function toRows(found: Found): Row[] {
    return [
      ...found.notes.map((n) => ({
        id: `note:${n.path}`,
        group: "Notes",
        label: n.title,
        hint: n.snippet || n.path,
        run: () => onnote(n.path),
      })),
      ...found.agents.map((a) => ({
        id: `agent:${a.id}`,
        group: "Agents",
        label: a.name,
        hint: a.id,
        run: () => onagent(a.id),
      })),
      ...found.messages.map((m) => ({
        id: `message:${m.id}`,
        group: "Messages",
        label: m.subject || "(no subject)",
        hint: `${m.from} to ${m.to}${m.snippet ? ` · ${m.snippet}` : ""}`,
        run: tab("inbox"),
      })),
      ...found.tasks.map((t) => ({
        id: `task:${t.id}`,
        group: "Tasks",
        label: `${t.id} ${t.title}`,
        hint: t.status,
        run: tab("tasks"),
      })),
      ...found.events.map((e) => ({
        id: `event:${e.id}`,
        group: "Calendar",
        label: e.title,
        hint: `${e.date} ${e.time}`.trim(),
        run: ondashboards,
      })),
    ];
  }

  $effect(() => {
    const text = query;
    clearTimeout(timer);
    active = 0;
    if (!text.trim()) {
      rows = [];
      searched = false;
      return;
    }
    timer = window.setTimeout(async () => {
      const mine = ++asked;
      busy = true;
      try {
        const found = await invoke<Found>("sidecar_call", {
          method: "search_all",
          params: { query: text },
        });
        if (mine !== asked) return;
        rows = toRows(found);
        error = null;
      } catch (cause) {
        if (mine === asked) error = String(cause);
      } finally {
        if (mine === asked) {
          searched = true;
          busy = false;
        }
      }
    }, 250);
  });

  onMount(() => input?.focus());

  function choose(row: Row | undefined): void {
    if (!row) return;
    onclose();
    row.run();
  }

  function onKey(e: KeyboardEvent): void {
    if (e.key === "Escape") {
      e.stopPropagation();
      onclose();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      active = Math.min(active + 1, rows.length - 1);
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      active = Math.max(active - 1, 0);
    } else if (e.key === "Enter") {
      e.preventDefault();
      choose(rows[active]);
    }
  }
</script>

<Dialog title="Search everything" {onclose} bare>
  <input
    bind:this={input}
    bind:value={query}
    onkeydown={onKey}
    placeholder="Search notes, messages, tasks, events and agents"
    aria-label="Search everything"
    autocomplete="off"
    role="combobox"
    aria-expanded="true"
    aria-controls="search-all-list"
    aria-activedescendant={rows[active] ? `search-all-${active}` : undefined}
  />
  <ul id="search-all-list" role="listbox" aria-label="Results">
    {#each rows as row, i (row.id)}
      {#if i === 0 || rows[i - 1]?.group !== row.group}
        <li class="group" role="presentation">{row.group}</li>
      {/if}
      <li role="presentation">
        <button
          type="button"
          id="search-all-{i}"
          role="option"
          tabindex="-1"
          aria-selected={i === active}
          class:active={i === active}
          onmouseenter={() => (active = i)}
          onclick={() => choose(row)}
        >
          <span class="label">{row.label}</span>
          <span class="hint">{row.hint}</span>
        </button>
      </li>
    {:else}
      {#if busy}<li class="muted" role="presentation">Searching…</li>
      {:else if searched}<li class="muted" role="presentation">
          No matches.
        </li>{/if}
    {/each}
  </ul>
  {#if error}<p class="muted" role="alert">{error}</p>{/if}
</Dialog>

<style>
  input {
    font: inherit;
    min-width: 0;
    color: var(--color-text);
    background: var(--color-bg-0);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    padding: var(--space-1) var(--space-2);
  }
  ul {
    margin: 0;
    padding: 0;
    overflow-y: auto;
    list-style: none;
  }
  .group {
    padding: var(--space-2) var(--space-2) var(--space-1);
    font-size: var(--font-size-xs);
    letter-spacing: 0.04em;
    text-transform: uppercase;
    color: var(--color-text-muted);
  }
  button {
    width: 100%;
    display: grid;
    gap: 2px;
    font: inherit;
    text-align: start;
    color: var(--color-text);
    background: none;
    border: 0;
    border-radius: var(--radius-sm);
    padding: var(--space-1) var(--space-2);
    cursor: pointer;
  }
  button.active {
    background: var(--color-surface);
    color: var(--color-link);
  }
  .hint,
  .muted {
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }
  .hint {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
</style>
