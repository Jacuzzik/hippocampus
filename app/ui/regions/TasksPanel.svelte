<!-- The office task board, read only: tasks grouped by status, as in the office app's Tasks page.
     A card that is not done can start a temp (a short-lived helper) on its text; the board itself is not changed. -->
<script lang="ts">
  import PanelHeader from "../controls/PanelHeader.svelte";
  import OwnerCards from "./OwnerCards.svelte";
  import Loading from "../controls/Loading.svelte";
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
    waiting?: boolean;
  };

  const STATUSES = ["todo", "doing", "blocked", "done"];

  let tasks = $state<Task[]>([]);
  let failed = $state(false);
  // False until the first answer (or failure), so an empty list is not shown while it is still loading.
  let loaded = $state(false);

  // Read again every few seconds while this tab is open, so it does not go stale.
  async function load(): Promise<void> {
    try {
      tasks = (
        await invoke<{ tasks: Task[] }>("sidecar_call", { method: "tasks" })
      ).tasks;
      failed = false;
      loaded = true;
    } catch (cause) {
      failed = true;
      loaded = true;
      console.error("Could not read the task board", cause);
    }
  }
  onMount(() => {
    void load();
    return flagOn("panelRefresh") ? every(load, 5000) : undefined;
  });

  // 7.23: one temp per click, on the card's id and title. The cap of running temps is the backend's.
  let tempNote = $state<{ id: string; text: string; bad: boolean } | null>(
    null,
  );
  async function startTemp(task: Task): Promise<void> {
    try {
      await invoke("sidecar_call", {
        method: "start_helper",
        params: {
          prompt: `Work on task ${task.id}: ${task.title}. Reply in a few lines with what you found or did.`,
        },
      });
      tempNote = {
        id: task.id,
        text: "Temp started. Its answer shows in the Temps tab.",
        bad: false,
      };
    } catch (cause) {
      tempNote = { id: task.id, text: String(cause), bad: true };
    }
  }

  const groups = $derived(
    STATUSES.map((status) => ({
      status,
      items: tasks.filter((t) => t.status === status),
    })),
  );
</script>

<section class="tasks" aria-label="Tasks">
  {#if !loaded}
    <Loading what="the task board" />
  {:else if failed}
    <p class="muted">Could not read the task board.</p>
  {:else if tasks.length === 0}
    <p class="muted">No tasks yet.</p>
  {:else}
    {#each groups as group (group.status)}
      <PanelHeader
        title={group.status.toUpperCase()}
        aside={String(group.items.length)}
      />
      {#if group.items.length}
        <ul>
          {#each group.items as task (task.id)}
            <li>
              <span class="id">{task.id}</span>
              <span>{task.title}</span>
              {#if task.waiting}<span class="waiting">Waiting on you</span>{/if}
              <small>{task.assignee ?? "unassigned"}</small>
              {#if task.status !== "done"}
                <button
                  type="button"
                  class="temp"
                  aria-label="Start a temp on {task.id}"
                  onclick={() => startTemp(task)}>Temp</button
                >
              {/if}
            </li>
            {#if tempNote?.id === task.id}
              <li class="note" class:bad={tempNote.bad} role="status">
                {tempNote.text}
              </li>
            {/if}
          {/each}
        </ul>
      {:else}
        <p class="muted">None.</p>
      {/if}
    {/each}
  {/if}
  <OwnerCards />
</section>

<style>
  .tasks {
    font-family: var(--font-ui);
    font-size: var(--font-size-xs);
    color: var(--color-md-text);
    overflow-y: auto;
  }

  ul {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    padding: var(--space-1) 0;
    border-bottom: 1px solid var(--color-border);
  }

  .id {
    color: var(--color-md-text-subtle);
  }

  li small {
    margin-inline-start: auto;
    color: var(--color-md-text-muted);
  }

  .muted {
    color: var(--color-md-text-muted);
  }

  .temp {
    flex: none;
    min-height: var(--size-24);
    padding: 0 var(--space-2);
    font: inherit;
    color: var(--color-md-text);
    background: transparent;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    cursor: pointer;
  }

  .note {
    color: var(--color-md-text-muted);
    border-bottom: none;
  }

  .note.bad {
    color: var(--color-danger);
  }

  .waiting {
    color: var(--color-ds-warning);
  }
</style>
