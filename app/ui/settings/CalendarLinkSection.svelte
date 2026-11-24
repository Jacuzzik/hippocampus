<script lang="ts">
  import { onMount } from "svelte";
  import Button from "../controls/Button.svelte";
  import { call } from "./call";

  // Calendars (D.07): a calendar's private iCal address, kept in the keychain. Its events show here and in the daily brief.
  type Event = { date: string; time: string; title: string };
  type State = {
    connected: boolean;
    name: string;
    events: Event[];
    read_at: string;
  };
  let view = $state<State | null>(null);
  let link = $state("");
  let name = $state("");
  let error = $state("");
  let busy = $state(false);

  async function run(method: string, params = {}): Promise<void> {
    busy = true;
    error = "";
    try {
      view = await call<State>(method, params);
      link = "";
    } catch (cause) {
      error = String(cause);
    } finally {
      busy = false;
    }
  }
  onMount(() => void run("calendar_link_state"));
</script>

<section class="control-section" aria-labelledby="calendar-link-title">
  <h3 id="calendar-link-title">Calendar</h3>
  <p class="hint">
    In Google Calendar open Settings, pick your calendar, then Integrate
    calendar, and copy the "Secret address in iCal format". Outlook and iCloud
    give the same kind of link. It is kept in the system keychain. Events show
    here and in the daily brief.
  </p>
  {#if view && !view.connected}
    <form
      class="row"
      onsubmit={(e) => {
        e.preventDefault();
        void run("calendar_link_set", { url: link, name });
      }}
    >
      <input
        aria-label="Calendar name"
        placeholder="Name (optional)"
        bind:value={name}
      />
      <input
        aria-label="Secret iCal address"
        type="password"
        placeholder="https://calendar.google.com/calendar/ical/…/basic.ics"
        bind:value={link}
      />
      <Button type="submit" variant="primary" disabled={busy || !link.trim()}
        >Connect</Button
      >
    </form>
  {:else if view}
    <div class="row">
      <span>Connected: {view.name || "My calendar"}</span>
      <Button disabled={busy} onclick={() => void run("calendar_read")}
        >Read again</Button
      >
      <Button variant="ghost" onclick={() => void run("calendar_link_clear")}
        >Disconnect</Button
      >
    </div>
    {#if view.events.length === 0}
      <p class="muted">Nothing in the next two weeks.</p>
    {:else}
      <ul aria-label="Calendar events">
        {#each view.events.slice(0, 20) as event, i (event.date + event.time + event.title + i)}
          <li>
            <span class="mono">{event.date} {event.time || "all day"}</span>
            {event.title}
          </li>
        {/each}
      </ul>
    {/if}
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
</style>
