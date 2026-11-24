<script lang="ts">
  // 7.18: the built-in code editor for one agent's folder: a file tree, tabs, save, and git views.
  // Every file call goes through the backend, which refuses any path outside the folder.
  import { onMount, untrack } from "svelte";
  import { SvelteMap } from "svelte/reactivity";
  import Dialog from "../controls/Dialog.svelte";
  import Button from "../controls/Button.svelte";
  import { call } from "../settings/call";
  import { EditorView, makeState } from "./editorSetup";
  import type { EditorState } from "@codemirror/state";

  let {
    folder,
    name,
    onclose,
  }: { folder: string; name: string; onclose: () => void } = $props();

  type Row = { name: string; path: string; dir: boolean };
  type Tab = { path: string; saved: string; text: string };
  type Git = {
    repo: boolean;
    branch: string;
    files: { state: string; path: string }[];
    branches: string[];
  };
  type Commit = { sha: string; author: string; date: string; subject: string };
  type Versus = {
    base: string;
    head: string;
    ahead: number;
    behind: number;
    files: { state: string; path: string }[];
  };

  let children = $state<Record<string, Row[]>>({});
  let expanded = $state<Record<string, boolean>>({});
  let tabs = $state<Tab[]>([]);
  let current = $state("");
  let side = $state<"files" | "changes" | "history" | "compare">("files");
  let git = $state<Git | null>(null);
  let commits = $state<Commit[]>([]);
  let shown = $state("");
  let base = $state("");
  let head = $state("");
  let versus = $state<Versus | null>(null);
  let error = $state("");
  let note = $state("");
  let busy = $state(false);
  let host: HTMLDivElement | undefined = $state();
  let view: EditorView | undefined;
  const states = new SvelteMap<string, EditorState>();

  const active = $derived(tabs.find((t) => t.path === current));
  const dirty = (t: Tab): boolean => t.text !== t.saved;

  async function guarded<T>(work: () => Promise<T>): Promise<T | undefined> {
    busy = true;
    error = "";
    try {
      return await work();
    } catch (cause) {
      error = String(cause);
      return undefined;
    } finally {
      busy = false;
    }
  }

  async function list(path: string): Promise<void> {
    await guarded(async () => {
      const found = await call<{ rows: Row[] }>("editor_tree", {
        folder,
        path,
      });
      children[path] = found.rows;
    });
  }

  function toggle(row: Row): void {
    if (!row.dir) return void openFile(row.path);
    expanded[row.path] = !expanded[row.path];
    if (expanded[row.path] && !children[row.path]) void list(row.path);
  }

  function show(path: string): void {
    if (view && current) states.set(current, view.state);
    current = path;
    const tab = tabs.find((t) => t.path === path);
    if (!tab || !view) return;
    const state =
      states.get(path) ??
      makeState(
        path,
        tab.text,
        (text) => (tab.text = text),
        () => void save(),
      );
    view.setState(state);
  }

  async function openFile(path: string): Promise<void> {
    if (tabs.some((t) => t.path === path)) return show(path);
    const found = await guarded(() =>
      call<{ text: string }>("editor_read", { folder, path }),
    );
    if (!found) return;
    tabs.push({ path, saved: found.text, text: found.text });
    // The view mounts once there is a tab, so wait for the host before showing the first file.
    queueMicrotask(() => show(path));
  }

  function closeTab(path: string): void {
    const tab = tabs.find((t) => t.path === path);
    if (tab && dirty(tab) && !confirmClose.includes(path)) {
      confirmClose = [...confirmClose, path];
      return;
    }
    confirmClose = confirmClose.filter((p) => p !== path);
    states.delete(path);
    const at = tabs.findIndex((t) => t.path === path);
    tabs.splice(at, 1);
    if (current === path) {
      current = "";
      const next = tabs[Math.max(0, at - 1)];
      if (next) show(next.path);
    }
  }
  let confirmClose = $state<string[]>([]);

  async function save(): Promise<void> {
    const tab = active;
    if (!tab) return;
    const text = view?.state.doc.toString() ?? tab.text;
    const done = await guarded(() =>
      call("editor_save", { folder, path: tab.path, text }),
    );
    if (done) {
      tab.text = text;
      tab.saved = text;
      note = `Saved ${tab.path}.`;
      void loadGit();
    }
  }

  async function loadGit(): Promise<void> {
    const found = await guarded(() => call<Git>("editor_git", { folder }));
    if (!found) return;
    git = found;
    base ||= found.branches.find((b) => b !== found.branch) ?? "";
    head ||= found.branch;
  }

  async function showDiff(path: string): Promise<void> {
    const found = await guarded(() =>
      call<{ text: string }>("editor_diff", { folder, path }),
    );
    if (found) shown = found.text;
  }

  async function loadHistory(): Promise<void> {
    const found = await guarded(() =>
      call<{ rows: Commit[] }>("editor_history", {
        folder,
        path: active?.path ?? "",
      }),
    );
    if (found) commits = found.rows;
  }

  async function compare(): Promise<void> {
    const found = await guarded(() =>
      call<Versus>("editor_compare", { folder, base, head }),
    );
    if (found) versus = found;
  }

  function pick(next: typeof side): void {
    side = next;
    if (next !== "files") void loadGit();
    if (next === "history") void loadHistory();
  }

  onMount(() => {
    void list("");
    void loadGit();
    return () => {
      view?.destroy();
      view = undefined;
    };
  });

  // The view is made when its host element appears (the first open file) and rebuilt if that element is replaced.
  $effect(() => {
    const mount = host;
    untrack(() => {
      view?.destroy();
      view = undefined;
      if (!mount) return;
      view = new EditorView({ parent: mount });
      const keep = current;
      current = "";
      if (keep) show(keep);
    });
  });
</script>

{#snippet branch(rows: Row[], depth: number)}
  <ul
    class="tree"
    role={depth === 0 ? "tree" : "group"}
    aria-label={depth === 0 ? "Files" : undefined}
  >
    {#each rows as row (row.path)}
      <li
        role="treeitem"
        aria-selected={row.path === current}
        aria-expanded={row.dir ? !!expanded[row.path] : undefined}
      >
        <button
          type="button"
          class:on={row.path === current}
          style:padding-left="calc(var(--space-2) * {depth + 1})"
          onclick={() => toggle(row)}
          >{#if row.dir}<span aria-hidden="true"
              >{expanded[row.path] ? "▾ " : "▸ "}</span
            >{/if}{row.name}</button
        >
        {#if row.dir && expanded[row.path] && children[row.path]}
          {@render branch(children[row.path] ?? [], depth + 1)}
        {/if}
      </li>
    {/each}
  </ul>
{/snippet}

<Dialog
  title="Code editor"
  heading={`Code editor: ${name}`}
  {onclose}
  closeLabel="Close the editor"
  width="min(1100px, 96vw)"
  height="min(760px, 90vh)"
>
  <div class="editor">
    <aside>
      <div class="seg" role="group" aria-label="Editor views">
        {#each ["files", "changes", "history", "compare"] as const as id (id)}
          <button
            type="button"
            aria-pressed={side === id}
            onclick={() => pick(id)}>{id}</button
          >
        {/each}
      </div>
      {#if side === "files"}
        {@render branch(children[""] ?? [], 0)}
      {:else if !git}
        <p class="muted">Loading…</p>
      {:else if !git.repo}
        <p class="muted">This folder is not a git repository.</p>
      {:else if side === "changes"}
        <p class="muted">Branch {git.branch}</p>
        <ul class="list" aria-label="Changed files">
          {#each git.files as f (f.path)}
            <li>
              <button
                type="button"
                onclick={() => {
                  void openFile(f.path);
                  void showDiff(f.path);
                }}>{f.state} {f.path}</button
              >
            </li>
          {:else}
            <li class="muted">Nothing to commit.</li>
          {/each}
        </ul>
      {:else if side === "history"}
        <p class="muted">
          {active ? `History of ${active.path}` : "History of the folder"}
        </p>
        <Button disabled={busy} onclick={() => void loadHistory()}
          >Reload</Button
        >
        <ul class="list" aria-label="Commits">
          {#each commits as c (c.sha)}
            <li>
              <code>{c.sha}</code>
              {c.subject} <span class="muted">{c.author}, {c.date}</span>
            </li>
          {/each}
        </ul>
      {:else}
        <label
          >Base <select bind:value={base}
            >{#each git.branches as b (b)}<option value={b}>{b}</option
              >{/each}</select
          ></label
        >
        <label
          >Compare <select bind:value={head}
            >{#each git.branches as b (b)}<option value={b}>{b}</option
              >{/each}</select
          ></label
        >
        <Button disabled={busy || !base || !head} onclick={() => void compare()}
          >Compare branches</Button
        >
        {#if versus}
          <p role="status">
            {versus.head} is {versus.ahead} ahead and {versus.behind} behind {versus.base}.
          </p>
          <ul class="list" aria-label="Files that differ">
            {#each versus.files as f (f.path)}<li>
                {f.state}
                {f.path}
              </li>{:else}<li class="muted">No file differs.</li>{/each}
          </ul>
        {/if}
      {/if}
    </aside>
    <section class="main" aria-label="Editor">
      {#if tabs.length}
        <div class="tabs" role="tablist" aria-label="Open files">
          {#each tabs as t (t.path)}
            <span class="tab" class:on={t.path === current}>
              <button
                type="button"
                role="tab"
                aria-selected={t.path === current}
                onclick={() => show(t.path)}
                >{t.path.split("/").pop()}{dirty(t) ? " ●" : ""}</button
              >
              <button
                type="button"
                class="x"
                aria-label={confirmClose.includes(t.path)
                  ? `Close ${t.path} and lose changes`
                  : `Close ${t.path}`}
                onclick={() => closeTab(t.path)}
                >{confirmClose.includes(t.path) ? "discard?" : "×"}</button
              >
            </span>
          {/each}
          <span class="grow"></span>
          <Button
            disabled={busy || !active || !dirty(active)}
            onclick={() => void save()}>Save</Button
          >
        </div>
        <div class="cm" bind:this={host}></div>
      {:else}
        <p class="muted pad">Open a file from the tree. Ctrl+S saves.</p>
      {/if}
      {#if shown}<pre class="diff" aria-label="Diff">{shown}</pre>{/if}
      {#if note}<p class="muted pad" role="status">{note}</p>{/if}
      {#if error}<p class="error pad" role="alert">{error}</p>{/if}
    </section>
  </div>
</Dialog>

<style>
  .editor {
    display: grid;
    grid-template-columns: 260px 1fr;
    gap: var(--space-2);
    height: 100%;
    min-height: 0;
  }
  aside {
    overflow: auto;
    border-right: 1px solid var(--color-border);
    padding-right: var(--space-2);
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }
  .seg {
    display: flex;
    gap: var(--space-1);
  }
  .seg button[aria-pressed="true"] {
    background: var(--color-accent);
    color: var(--color-accent-on);
  }
  .tree,
  .list {
    list-style: none;
    margin: 0;
    padding: 0;
    font-size: var(--font-size-sm);
  }
  .tree button,
  .list button {
    display: block;
    width: 100%;
    text-align: left;
    background: none;
    border: none;
    color: inherit;
    cursor: pointer;
    padding-block: 2px;
  }
  .tree button.on {
    color: var(--color-accent);
  }
  .main {
    display: flex;
    flex-direction: column;
    min-height: 0;
    min-width: 0;
  }
  .tabs {
    display: flex;
    align-items: center;
    gap: var(--space-1);
    flex-wrap: wrap;
  }
  .tab {
    display: inline-flex;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
  }
  .tab.on {
    border-color: var(--color-accent);
  }
  .tab button {
    background: none;
    border: none;
    color: inherit;
    cursor: pointer;
    padding: 2px var(--space-2);
  }
  .grow {
    flex: 1;
  }
  .cm {
    flex: 1;
    min-height: 200px;
    overflow: hidden;
  }
  .diff {
    max-height: 30%;
    overflow: auto;
    margin: 0;
    font-size: var(--font-size-xs);
    white-space: pre-wrap;
  }
  .pad {
    padding: var(--space-2);
    margin: 0;
  }
</style>
