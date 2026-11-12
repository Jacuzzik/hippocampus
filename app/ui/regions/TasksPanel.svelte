<!-- The office task board, read only: tasks grouped by status, as in the office app's Tasks page. -->
<script lang="ts">
  import { onMount } from "svelte";
  import { every } from "../poll.ts";
  import { flagOn } from "../flags.svelte.ts";
  import { invoke } from "@tauri-apps/api/core";

  type Task = {
    id: string;
    title: string;
    status: string;
    assignee: string | null;
    updatedAt: string | null;
  };

  const STATUSES = ["todo", "doing", "blocked", "done"];

  let tasks = $state<Task[]>([]);
  let failed = $state(false);

  // Read again every few seconds while this tab is open, so it does not go stale.
  async function load(): Promise<void> {
    try {
      tasks = (await invoke<{ tasks: Task[] }>("sidecar_call", { method: "tasks" })).tasks;
      failed = false;
    } catch (cause) {
      failed = true;
      console.error("Could not read the task board", cause);
    }
  }
  onMount(() => {
    void load();
    return flagOn("panelRefresh") ? every(load, 5000) : undefined;
  });

  const groups = $derived(
    STATUSES.map((status) => ({ status, items: tasks.filter((t) => t.status === status) })),
  );
</script>

<section class="tasks" aria-label="Tasks">
  {#if failed}
    <p class="muted">Could not read the task board.</p>
  {:else if tasks.length === 0}
    <p class="muted">No tasks yet.</p>
  {:else}
    {#each groups as group (group.status)}
      <h3>{group.status.toUpperCase()} · {group.items.length}</h3>
      {#if group.items.length}
        <ul>
          {#each group.items as task (task.id)}
            <li>
              <span class="id">{task.id}</span>
              <span>{task.title}</span>
              <small>{task.assignee ?? "unassigned"}</small>
            </li>
          {/each}
        </ul>
      {:else}
        <p class="muted">None.</p>
      {/if}
    {/each}
  {/if}
</section>

<style>
  .tasks {
    font-family: var(--font-ui);
    font-size: var(--font-size-xs);
    color: var(--color-md-text);
    overflow-y: auto;
  }

  h3 {
    margin: var(--space-2) 0 var(--space-1);
    font-family: var(--font-ui);
    font-size: var(--font-size-tag);
    color: var(--color-md-accent);
  }

  ul {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    display: flex;
    gap: var(--space-2);
    align-items: baseline;
    padding: var(--space-1) 0;
    border-bottom: 1px solid var(--color-border);
  }

  .id {
    color: var(--color-md-text-subtle);
  }

  li small {
    margin-left: auto;
    color: var(--color-md-text-muted);
  }

  .muted {
    color: var(--color-md-text-muted);
  }
</style>
