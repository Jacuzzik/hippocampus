<script lang="ts">
  // The calendar dashboard: a week of time slots (or a month grid) with the user's events, the days
  // scheduled jobs run, and the next events up. At an event's time the backend sends it to its agent,
  // which reminds the user or does the work and answers done or not done: the event then shows a check
  // or a cross. Everything sits inside the board, so the dashboard lock covers every control here.
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import Button from "../controls/Button.svelte";
  import Dialog from "../controls/Dialog.svelte";
  import Dropdown from "../controls/Dropdown.svelte";
  import ErrorRow from "../controls/ErrorRow.svelte";
  import Loading from "../controls/Loading.svelte";
  import {
    STATUS_TEXT,
    addDays,
    lanes,
    minutesOf,
    monthCells,
    shiftMonth,
    weekDates,
    type CalendarEvent,
    type CalendarShape,
    type EventStatus,
  } from "./model.ts";

  const MAIN = "hippoherman";
  const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  let view = $state<CalendarShape | null>(null);
  let error = $state<string | null>(null);
  let formError = $state<string | null>(null);
  let mode = $state<"week" | "month">("week");
  let anchor = $state("");
  let day = $state("");
  let time = $state("");
  let title = $state("");
  let note = $state("");
  let agent = $state(MAIN);
  let openId = $state<string | null>(null);
  let now = $state(new Date());
  let scroller = $state<HTMLDivElement | undefined>();
  let scrolled = false;

  async function load(month?: string): Promise<void> {
    try {
      view = await invoke<CalendarShape>("sidecar_call", {
        method: "calendar",
        params: month ? { month } : {},
      });
      error = null;
      if (!anchor) anchor = view.today;
      if (!day) day = view.today;
    } catch (cause) {
      error = String(cause);
    }
  }

  onMount(() => {
    void load();
    // The agent's answer can come at any time: read the calendar again every half minute.
    const timer = setInterval(() => {
      now = new Date();
      if (view && !openId) void load(view.month);
    }, 30_000);
    return () => clearInterval(timer);
  });

  // The week opens at 07:00, the start of most days, instead of at midnight.
  $effect(() => {
    if (!scroller || scrolled) return;
    const seven = scroller.querySelector<HTMLElement>('[data-hour="7"]');
    if (seven) {
      scroller.scrollTop = seven.offsetTop - 8;
      scrolled = true;
    }
  });

  function ensure(): void {
    if (view && view.month !== anchor.slice(0, 7))
      void load(anchor.slice(0, 7));
  }

  function go(step: number): void {
    anchor =
      mode === "week"
        ? addDays(anchor, step * 7)
        : `${shiftMonth(anchor.slice(0, 7), step)}-01`;
    ensure();
  }

  function goToday(): void {
    if (!view) return;
    anchor = view.today;
    ensure();
  }

  // One write to the calendar; the backend answers with the month as it is now.
  async function call(run: () => Promise<CalendarShape>): Promise<boolean> {
    formError = null;
    try {
      view = await run();
      return true;
    } catch (cause) {
      formError = String(cause);
      return false;
    }
  }

  async function add(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    const ok = await call(() =>
      invoke<CalendarShape>("sidecar_call", {
        method: "calendar_add",
        params: { date: day, time, title, note, agent },
      }),
    );
    if (ok) {
      anchor = day;
      title = "";
      note = "";
    }
  }

  async function remove(id: string): Promise<void> {
    const ok = await call(() =>
      invoke<CalendarShape>("sidecar_call", {
        method: "calendar_remove",
        params: { id, month: view?.month },
      }),
    );
    if (ok) openId = null;
  }

  async function mark(id: string, status: EventStatus): Promise<void> {
    await call(() =>
      invoke<CalendarShape>("sidecar_call", {
        method: "calendar_mark",
        params: { id, status, month: view?.month },
      }),
    );
  }

  const opened = $derived(
    view?.events.find((event) => event.id === openId) ?? null,
  );
  const week = $derived(anchor ? weekDates(anchor) : []);
  const statusOf = (event: CalendarEvent): EventStatus =>
    event.status ?? "scheduled";
  const on = (date: string): CalendarEvent[] =>
    view?.events.filter((event) => event.date === date) ?? [];
  const jobsOn = (date: string): string[] =>
    view?.job_runs.filter((run) => run.date === date).map((run) => run.name) ??
    [];
  const cells = $derived(view ? monthCells(view) : []);
  const nowMinutes = $derived(now.getHours() * 60 + now.getMinutes());
  const clock = $derived(
    `${String(now.getHours()).padStart(2, "0")}:${String(now.getMinutes()).padStart(2, "0")}`,
  );
  const agents = $derived(
    (view?.agents?.length ? view.agents : [MAIN]).map((id) => ({
      value: id,
      label: id === MAIN ? "Hippoherman (main agent)" : id,
    })),
  );

  function longDate(iso: string, options: Intl.DateTimeFormatOptions): string {
    return new Date(`${iso}T00:00:00`).toLocaleDateString([], options);
  }
  const heading = $derived.by(() => {
    if (!anchor) return "";
    if (mode === "month")
      return longDate(`${anchor.slice(0, 7)}-01`, {
        month: "long",
        year: "numeric",
      });
    const [first = anchor, last = anchor] = [week[0], week[6]];
    return `${longDate(first, { month: "short", day: "numeric" })} – ${longDate(last, { month: "short", day: "numeric", year: "numeric" })}`;
  });
  const todayCount = $derived(view ? on(view.today).length : 0);
  const when = (event: CalendarEvent): string =>
    `${longDate(event.date, { weekday: "short", day: "numeric", month: "short" })} · ${event.time || "All day"}`;
</script>

{#snippet icon(status: EventStatus)}
  <span class="icon {status}" aria-hidden="true">
    <svg
      width="12"
      height="12"
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      stroke-width="2.2"
      stroke-linecap="round"
      stroke-linejoin="round"
    >
      {#if status === "done"}
        <path d="M3 8.5 6.5 12 13 4.5" />
      {:else if status === "failed"}
        <path d="M4 4l8 8M12 4l-8 8" />
      {:else if status === "sent"}
        <circle cx="3.5" cy="8" r="0.6" /><circle
          cx="8"
          cy="8"
          r="0.6"
        /><circle cx="12.5" cy="8" r="0.6" />
      {:else if status === "missed"}
        <circle cx="8" cy="8" r="5.5" /><path d="M4.2 11.8 11.8 4.2" />
      {:else}
        <circle cx="8" cy="8" r="5.5" /><path d="M8 5v3.2l2 1.3" />
      {/if}
    </svg>
  </span>
{/snippet}

{#if error && !view}
  <ErrorRow message={error} onretry={() => load(view?.month)} />
{:else if view === null}
  <Loading what="the calendar" />
{:else}
  <div class="top">
    <section class="upcoming" aria-label="Upcoming">
      <div class="today-tile">
        <b>{longDate(view.today, { month: "short", day: "numeric" })}</b>
        <span>
          {longDate(view.today, { weekday: "long" })}<br />
          {todayCount}
          {todayCount === 1 ? "event" : "events"} today
        </span>
      </div>
      <div class="next">
        <h3>Upcoming</h3>
        {#each view.upcoming ?? [] as event (event.id)}
          <button
            type="button"
            class="up {statusOf(event)}"
            onclick={() => (openId = event.id)}
          >
            <span class="text">
              <span class="name">{event.title}</span>
              <span class="meta"
                >{when(event)} · {STATUS_TEXT[statusOf(event)]}</span
              >
            </span>
          </button>
        {:else}
          <p class="quiet">
            Nothing coming up. Add an event and its agent gets it at that time.
          </p>
        {/each}
      </div>
    </section>

    <form class="add" onsubmit={add} aria-label="New event">
      <label class="wide"
        >Event <input
          type="text"
          maxlength="120"
          placeholder="Send the weekly report to the team"
          bind:value={title}
        /></label
      >
      <label>Date <input type="date" bind:value={day} required /></label>
      <label>Time <input type="time" bind:value={time} /></label>
      <div class="agent">
        <span>Agent</span>
        <Dropdown label="Agent" options={agents} bind:value={agent} />
      </div>
      <label class="wide"
        >Details <input
          type="text"
          maxlength="1000"
          placeholder="Anything the agent needs to know (optional)"
          bind:value={note}
        /></label
      >
      <Button type="submit" variant="primary" disabled={!title.trim() || !day}
        >Add event</Button
      >
      <p class="hint">
        At this time the agent gets it, reminds you or does the work, and the
        event gets a check when it is completed or a cross when it is not. No
        time means 09:00.
      </p>
    </form>
  </div>
  {#if formError}<p class="error" role="alert">{formError}</p>{/if}

  <div class="bar">
    <span class="range" aria-live="polite">{heading}</span>
    <button
      type="button"
      class="nav"
      aria-label={mode === "week" ? "Previous week" : "Previous month"}
      onclick={() => go(-1)}>‹</button
    >
    <button
      type="button"
      class="nav"
      aria-label={mode === "week" ? "Next week" : "Next month"}
      onclick={() => go(1)}>›</button
    >
    <span class="grow"></span>
    <button type="button" class="pill" onclick={goToday}>Today</button>
    <div class="switch" role="group" aria-label="Calendar view">
      <button
        type="button"
        class="pill"
        aria-pressed={mode === "week"}
        onclick={() => (mode = "week")}>Week</button
      >
      <button
        type="button"
        class="pill"
        aria-pressed={mode === "month"}
        onclick={() => {
          mode = "month";
          ensure();
        }}>Month</button
      >
    </div>
  </div>

  {#if mode === "week"}
    <div class="week">
      <div class="row head">
        <span class="gutter"></span>
        {#each week as date, i (date)}
          <span
            class="dayhead"
            class:today={date === view.today}
            class:past={date < view.today}
          >
            <small>{WEEKDAYS[i]}</small>
            <b>{date.slice(8)}/{date.slice(5, 7)}</b>
          </span>
        {/each}
      </div>
      <div class="row allday">
        <span class="gutter">All day</span>
        {#each week as date (date)}
          <div class="slot" role="group" aria-label={`All day ${date}`}>
            {#each jobsOn(date) as job (job)}
              <span class="job" title="A scheduled job runs on this day"
                >{job}</span
              >
            {/each}
            {#each on(date).filter((event) => !event.time) as event (event.id)}
              <button
                type="button"
                class="chip {statusOf(event)}"
                onclick={() => (openId = event.id)}
              >
                {@render icon(statusOf(event))}<span class="text"
                  >{event.title}</span
                >
              </button>
            {/each}
          </div>
        {/each}
      </div>
      <div class="hours" bind:this={scroller}>
        <div class="row body">
          <div class="gutter labels">
            {#each Array.from({ length: 24 }, (_, h) => h) as h (h)}
              <span data-hour={h}>{String(h).padStart(2, "0")}:00</span>
            {/each}
          </div>
          {#each week as date (date)}
            {@const timed = on(date).filter((event) => event.time)}
            {@const placed = lanes(timed)}
            <div
              class="col"
              class:today={date === view.today}
              role="group"
              aria-label={date}
            >
              {#each timed as event (event.id)}
                {@const at = placed.get(event.id) ?? { lane: 0, of: 1 }}
                <button
                  type="button"
                  class="card {statusOf(event)}"
                  style:top={`calc(${minutesOf(event.time) / 60} * var(--hour) + 2px)`}
                  style:left={`calc(${(at.lane / at.of) * 100}% + 2px)`}
                  style:width={`calc(${100 / at.of}% - 4px)`}
                  aria-label={`${event.time} ${event.title}, ${STATUS_TEXT[statusOf(event)]}`}
                  onclick={() => (openId = event.id)}
                >
                  <span class="cardtop"
                    >{@render icon(statusOf(event))}<span>{event.time}</span
                    ></span
                  >
                  <span class="name">{event.title}</span>
                </button>
              {/each}
            </div>
          {/each}
          {#if week.includes(view.today)}
            <div
              class="now"
              style:top={`calc(${nowMinutes / 60} * var(--hour))`}
              aria-hidden="true"
            >
              <span>{clock}</span>
            </div>
          {/if}
        </div>
      </div>
    </div>
  {:else}
    <div class="grid" role="grid" aria-label={heading}>
      {#each WEEKDAYS as name (name)}
        <span class="weekday" role="columnheader">{name}</span>
      {/each}
      {#each cells as cell, i (i)}
        {#if cell === null}
          <span class="blank" role="presentation"></span>
        {:else}
          <div
            class="mday"
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
              <button
                type="button"
                class="chip {statusOf(event)}"
                onclick={() => (openId = event.id)}
              >
                {@render icon(statusOf(event))}<span class="text"
                  >{event.time ? `${event.time} ` : ""}{event.title}</span
                >
              </button>
            {/each}
          </div>
        {/if}
      {/each}
    </div>
  {/if}
{/if}

{#if opened}
  <Dialog
    title={opened.title}
    onclose={() => (openId = null)}
    closeLabel="Close"
    width="min(440px, 90vw)"
  >
    <div class="detail">
      <p class="state {statusOf(opened)}">
        {@render icon(statusOf(opened))}
        <b>{STATUS_TEXT[statusOf(opened)]}</b>
      </p>
      <dl>
        <dt>When</dt>
        <dd>{when(opened)}</dd>
        <dt>Agent</dt>
        <dd>
          {opened.agent === MAIN || !opened.agent
            ? "Hippoherman (main agent)"
            : opened.agent}
        </dd>
        {#if opened.note}<dt>Details</dt>
          <dd>{opened.note}</dd>{/if}
        {#if opened.result}<dt>Answer</dt>
          <dd>{opened.result}</dd>{/if}
      </dl>
      <div class="actions">
        {#if statusOf(opened) !== "done"}
          <Button size="sm" onclick={() => mark(opened.id, "done")}
            >Mark completed</Button
          >
        {/if}
        {#if statusOf(opened) !== "failed"}
          <Button size="sm" onclick={() => mark(opened.id, "failed")}
            >Mark not completed</Button
          >
        {/if}
        {#if statusOf(opened) !== "scheduled"}
          <Button size="sm" onclick={() => mark(opened.id, "scheduled")}
            >Send again</Button
          >
        {/if}
        <Button
          size="sm"
          variant="danger"
          aria-label={`Remove ${opened.title}`}
          onclick={() => remove(opened.id)}>Remove</Button
        >
      </div>
      {#if formError}<p class="error" role="alert">{formError}</p>{/if}
    </div>
  </Dialog>
{/if}

<style>
  /* Status colours: a soft tint of the meaning colour over the card, the icon in the full colour. */
  .scheduled {
    --tone: var(--color-text-muted);
    --tint: var(--color-bg-1);
  }
  .sent {
    --tone: var(--color-accent);
    --tint: color-mix(in srgb, var(--color-accent) 22%, var(--color-bg-1));
  }
  .done {
    --tone: var(--color-success);
    --tint: color-mix(in srgb, var(--color-success) 18%, var(--color-bg-1));
  }
  .failed {
    --tone: var(--color-danger);
    --tint: color-mix(in srgb, var(--color-danger) 18%, var(--color-bg-1));
  }
  .missed {
    --tone: var(--color-text-subtle);
    --tint: var(--color-bg-0);
  }

  .icon {
    display: inline-grid;
    flex: none;
    place-items: center;
    width: var(--size-18);
    height: var(--size-18);
    color: var(--color-bg-0);
    background: var(--tone);
    border-radius: 50%;
  }

  .icon.scheduled,
  .icon.missed {
    color: var(--tone);
    background: none;
  }

  /* Top row: the Upcoming card and the new-event form side by side; stacked when narrow. */
  .top {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1.4fr);
    gap: var(--space-3);
    margin-top: var(--space-3);
  }

  @media (max-width: 900px) {
    .top {
      grid-template-columns: minmax(0, 1fr);
    }
  }

  .upcoming {
    display: flex;
    gap: var(--space-3);
    padding: var(--space-3);
    background: var(--pop-bg);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
  }

  .today-tile {
    display: flex;
    flex: none;
    flex-direction: column;
    justify-content: space-between;
    align-self: start;
    width: var(--size-140);
    aspect-ratio: 1;
    padding: var(--space-3);
    color: var(--color-accent-on);
    background: var(--color-accent);
    border-radius: var(--radius-md);
  }

  .today-tile b {
    font-size: var(--font-size-xl);
    line-height: 1.1;
  }

  .today-tile span {
    font-size: var(--font-size-sm);
    line-height: 1.35;
  }

  .next {
    display: flex;
    flex: 1;
    flex-direction: column;
    gap: var(--space-2);
    min-width: 0;
  }

  .next h3 {
    margin: 0;
    font-size: var(--font-size-md);
    font-weight: 500;
  }

  .up {
    display: flex;
    gap: var(--space-2);
    padding: 0 0 0 var(--space-2);
    color: var(--color-text);
    font: inherit;
    text-align: start;
    background: none;
    border: 0;
    border-left: 3px solid var(--tone);
    cursor: pointer;
  }

  .up.scheduled {
    border-left-color: var(--color-accent);
  }

  .up .text,
  .chip .text {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .up .name,
  .card .name,
  .chip .text {
    overflow: hidden;
    white-space: nowrap;
    text-overflow: ellipsis;
  }

  .up .meta {
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }

  .quiet,
  .hint {
    margin: 0;
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }

  .add {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: end;
    align-content: start;
    padding: var(--space-3);
    background: var(--pop-bg);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
  }

  .add label,
  .agent {
    display: flex;
    flex-direction: column;
    gap: var(--space-0);
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }

  .add .wide {
    flex: 1 1 var(--size-240);
  }

  .agent {
    width: var(--size-200);
  }

  .hint {
    flex-basis: 100%;
  }

  /* The bar over the calendar: the range, arrows, Today and the Week or Month switch. */
  .bar {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: center;
    margin-top: var(--space-3);
  }

  .range {
    padding: var(--space-1) var(--space-3);
    color: var(--color-accent-on);
    font-size: var(--font-size-sm);
    background: var(--color-accent);
    border-radius: 999px;
  }

  .grow {
    flex: 1;
  }

  .nav,
  .pill {
    min-height: var(--size-28);
    padding: 0 var(--space-3);
    color: var(--color-text);
    font: inherit;
    font-size: var(--font-size-sm);
    background: var(--color-bg-1);
    border: 1px solid var(--color-border);
    border-radius: 999px;
    cursor: pointer;
  }

  .nav {
    width: var(--size-28);
    padding: 0;
  }

  .nav:hover,
  .pill:hover {
    border-color: var(--color-accent);
  }

  .switch {
    display: flex;
    gap: var(--space-0);
    padding: 2px;
    background: var(--color-bg-1);
    border: 1px solid var(--color-border);
    border-radius: 999px;
  }

  .switch .pill {
    border: 0;
    background: none;
  }

  .switch .pill[aria-pressed="true"] {
    color: var(--color-accent-on);
    background: var(--color-accent);
  }

  /* Week: day headers, an all-day row, then 24 hour rows that scroll. */
  .week {
    --hour: var(--size-64);
    --gutter: var(--size-52);
    display: flex;
    flex: 1 1 auto;
    flex-direction: column;
    min-height: var(--size-420);
    margin-top: var(--space-3);
  }

  .row {
    display: grid;
    grid-template-columns: var(--gutter) repeat(7, minmax(0, 1fr));
    gap: var(--space-1);
  }

  .head,
  .allday {
    overflow-y: hidden;
    scrollbar-gutter: stable;
  }

  .gutter {
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }

  .dayhead {
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: var(--space-1) 0;
    color: var(--color-text);
    background: var(--color-bg-1);
    border-radius: var(--radius-md);
  }

  .dayhead small {
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .dayhead.past b {
    color: var(--color-text-muted);
  }

  .dayhead.today {
    color: var(--color-accent-on);
    background: var(--color-accent);
  }

  .dayhead.today small {
    color: inherit;
  }

  .allday {
    margin-top: var(--space-1);
  }

  .allday .gutter {
    align-self: center;
  }

  .slot {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-height: var(--size-24);
  }

  .job {
    overflow: hidden;
    padding: 0 var(--space-1);
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
    white-space: nowrap;
    text-overflow: ellipsis;
    border: 1px dashed var(--color-border);
    border-radius: var(--radius-sm);
  }

  .chip {
    display: flex;
    gap: var(--space-1);
    align-items: center;
    min-width: 0;
    padding: 1px var(--space-1);
    color: var(--color-text);
    font: inherit;
    font-size: var(--font-size-xs);
    text-align: start;
    background: var(--tint);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    cursor: pointer;
  }

  .hours {
    flex: 1 1 0;
    min-height: var(--size-240);
    margin-top: var(--space-1);
    overflow-y: auto;
    scrollbar-gutter: stable;
  }

  .body {
    position: relative;
  }

  .labels span {
    display: block;
    height: var(--hour);
    transform: translateY(-0.6em);
  }

  .labels span:first-child {
    transform: none;
  }

  .col {
    position: relative;
    height: calc(24 * var(--hour));
    background-image: repeating-linear-gradient(
      to bottom,
      var(--color-border) 0 1px,
      transparent 1px var(--hour)
    );
    border-radius: var(--radius-sm);
  }

  .col.today {
    background-color: color-mix(in srgb, var(--color-accent) 6%, transparent);
  }

  .card {
    position: absolute;
    display: flex;
    flex-direction: column;
    gap: 2px;
    height: calc(var(--hour) - 4px);
    padding: var(--space-1) var(--space-2);
    overflow: hidden;
    color: var(--color-text);
    font: inherit;
    font-size: var(--font-size-xs);
    text-align: start;
    background: var(--tint);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    cursor: pointer;
  }

  .card.missed {
    border-style: dashed;
    color: var(--color-text-muted);
  }

  .card:hover,
  .chip:hover {
    border-color: var(--tone);
  }

  .card.scheduled:hover,
  .chip.scheduled:hover {
    border-color: var(--color-accent);
  }

  .cardtop {
    display: flex;
    gap: var(--space-1);
    align-items: center;
    color: var(--color-text-muted);
  }

  .card .name {
    font-size: var(--font-size-sm);
  }

  .now {
    position: absolute;
    inset-inline-end: 0;
    inset-inline-start: var(--gutter);
    border-top: 1px dashed var(--color-accent);
    pointer-events: none;
  }

  .now span {
    position: absolute;
    top: 0;
    inset-inline-start: calc(-1 * var(--gutter));
    padding: 0 var(--space-1);
    color: var(--color-accent-on);
    font-size: var(--font-size-xs);
    background: var(--color-accent);
    border-radius: 999px;
    transform: translateY(-50%);
  }

  /* Month: the whole month, a cell per day. */
  .grid {
    flex: 1 1 auto;
    display: grid;
    grid-template-columns: repeat(7, minmax(0, 1fr));
    grid-template-rows: auto;
    grid-auto-rows: minmax(var(--size-96), 1fr);
    gap: var(--space-1);
    margin-top: var(--space-3);
  }

  .grid .weekday {
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
    text-align: center;
    text-transform: uppercase;
    letter-spacing: 0.06em;
  }

  .mday {
    display: flex;
    flex-direction: column;
    gap: 2px;
    min-width: 0;
    padding: var(--space-1);
    background: var(--color-bg-1);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
  }

  .mday.today {
    border-color: var(--color-accent);
  }

  .number {
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }

  .today .number {
    color: var(--color-accent);
  }

  .detail {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
  }

  .state {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    margin: 0;
    color: var(--tone);
  }

  dl {
    display: grid;
    grid-template-columns: auto minmax(0, 1fr);
    gap: var(--space-1) var(--space-3);
    margin: 0;
  }

  dt {
    color: var(--color-text-muted);
  }

  dd {
    margin: 0;
    overflow-wrap: anywhere;
  }

  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }

  .error {
    color: var(--color-danger);
  }
</style>
