<!-- The office task board, read only: tasks grouped by status, as in Munder Difflin's Tasks page. -->
<script lang="ts">
  import { onMount } from "svelte";
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

  onMount(async () => {
    try {
      tasks = (await invoke<{ tasks: Task[] }>("sidecar_call", { method: "tasks" })).tasks;
    } catch (cause) {
      failed = true;
      console.error("Could not read the task board", cause);
    }
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
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
    color: var(--color-md-text);
    overflow-y: auto;
  }

  h3 {
    margin: var(--space-2) 0 var(--space-1);
    font-family: "Press Start 2P", monospace;
    font-size: 8px;
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
