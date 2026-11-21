<script lang="ts">
  // The calendar dashboard: one month of the user's own events and the days scheduled jobs will run.
  // Events are kept on this computer by the backend. Everything here sits inside the board, so the
  // dashboard lock covers the month buttons, the form and the remove buttons.
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import ErrorRow from "../controls/ErrorRow.svelte";
  import Loading from "../controls/Loading.svelte";
  import { monthCells, shiftMonth, type CalendarShape } from "./model.ts";

  let view = $state<CalendarShape | null>(null);
  let error = $state<string | null>(null);
  let formError = $state<string | null>(null);
  let day = $state("");
  let time = $state("");
  let title = $state("");

  async function show(month?: string): Promise<void> {
    error = null;
    try {
      view = await invoke<CalendarShape>("sidecar_call", {
        method: "calendar",
        params: month ? { month } : {},
      });
      if (!day) day = view.today;
    } catch (cause) {
      error = String(cause);
    }
  }
  onMount(() => void show());

  async function add(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    formError = null;
    try {
      view = await invoke<CalendarShape>("sidecar_call", {
        method: "calendar_add",
        params: { date: day, time, title },
      });
      title = "";
    } catch (cause) {
      formError = String(cause);
    }
  }

  async function remove(id: string): Promise<void> {
    formError = null;
    try {
      view = await invoke<CalendarShape>("sidecar_call", {
        method: "calendar_remove",
        params: { id, month: view?.month },
      });
    } catch (cause) {
      formError = String(cause);
    }
  }

  const cells = $derived(view ? monthCells(view) : []);
  const heading = $derived(
    view
      ? new Date(`${view.month}-01T00:00:00`).toLocaleDateString([], {
          month: "long",
          year: "numeric",
        })
      : "",
  );
</script>

{#if error}
  <ErrorRow message={error} onretry={() => show(view?.month)} />
{:else if view === null}
  <Loading what="the calendar" />
{:else}
  <div class="bar">
    <button
      type="button"
      aria-label="Previous month"
      onclick={() => view && show(shiftMonth(view.month, -1))}>‹</button
    >
    <b aria-live="polite">{heading}</b>
    <button
      type="button"
      aria-label="Next month"
      onclick={() => view && show(shiftMonth(view.month, 1))}>›</button
    >
    <button type="button" onclick={() => show()}>This month</button>
  </div>
  <div class="grid" role="grid" aria-label={heading}>
    {#each ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as name (name)}
      <span class="weekday" role="columnheader">{name}</span>
    {/each}
    {#each cells as cell, i (i)}
      {#if cell === null}
        <span class="blank" role="presentation"></span>
      {:else}
        <div
          class="day"
          class:today={cell.date === view.today}
          role="gridcell"
          aria-label={cell.date}
        >
          <span class="number">{cell.day}</span>
          {#each cell.jobs as job (job)}
            <span class="job" title="A scheduled job runs on this day"
              >{job}</span
            >
          {/each}
          {#each cell.events as event (event.id)}
            <span class="event">
              <span class="text"
                >{event.time ? `${event.time} ` : ""}{event.title}</span
              >
              <button
                type="button"
                aria-label={`Remove ${event.title}`}
                onclick={() => remove(event.id)}>×</button
              >
            </span>
          {/each}
        </div>
      {/if}
    {/each}
  </div>
  <form class="add" onsubmit={add}>
    <label>Date <input type="date" bind:value={day} required /></label>
    <label>Time <input type="time" bind:value={time} /></label>
    <label class="wide"
      >Event <input
        type="text"
        maxlength="120"
        placeholder="What happens"
        bind:value={title}
      /></label
    >
    <button type="submit" disabled={!title.trim() || !day}>Add event</button>
  </form>
  {#if formError}<p class="error" role="alert">{formError}</p>{/if}
{/if}

<style>
  .bar,
  .add {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: end;
    margin-top: var(--space-3);
  }

  .bar {
    align-items: center;
  }

  .bar b {
    min-width: 12ch;
    text-align: center;
  }

  button,
  input {
    min-height: var(--size-28);
    padding: var(--space-1) var(--space-2);
    color: var(--color-text);
    font: inherit;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
  }

  button {
    cursor: pointer;
  }

  /* The month grows to fill the dashboard: the weekday row keeps its height, the weeks share the rest. */
  .grid {
    flex: 1 1 auto;
    display: grid;
    grid-template-columns: repeat(7, minmax(0, 1fr));
    grid-template-rows: auto;
    grid-auto-rows: minmax(var(--size-64), 1fr);
    gap: var(--space-1);
    margin-top: var(--space-3);
  }

  .weekday {
    color: var(--color-text-muted);
    text-align: center;
  }

  .day {
    display: flex;
    flex-direction: column;
    gap: var(--space-0);
    min-height: var(--size-64);
    padding: var(--space-1);
    background: var(--color-bg-1);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
  }

  .day.today {
    border-color: var(--color-accent);
  }

  .number {
    color: var(--color-text-muted);
  }

  .today .number {
    color: var(--color-accent);
  }

  .job,
  .event {
    overflow-wrap: anywhere;
    font-size: var(--font-size-xs);
  }

  .job {
    color: var(--color-text-muted);
  }

  .event {
    display: flex;
    gap: var(--space-1);
    align-items: start;
    justify-content: space-between;
  }

  .event button {
    min-width: var(--size-24);
    min-height: var(--size-24);
    padding: 0;
    color: var(--color-text-muted);
    background: none;
    border: 0;
  }

  .add label {
    display: flex;
    flex-direction: column;
    gap: var(--space-0);
    color: var(--color-text-muted);
  }

  .add .wide {
    flex: 1;
    min-width: var(--size-200);
  }

  .error {
    color: var(--color-danger);
  }
</style>
