<!-- K.15 Scheduled missions: a message sent to an agent on a schedule (core/missions.py). Shown inside Triggers, so
     the notes jobs and the missions are one schedule list. A new mission starts switched off. -->
<script lang="ts">
  import Button from "../controls/Button.svelte";
  import Toggle from "../controls/Toggle.svelte";
  import Loading from "../controls/Loading.svelte";
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import { report } from "../notices.svelte.ts";
  import { addedAgents, archived } from "../owner/addedAgents.svelte";

  type Mission = {
    id: string;
    label: string;
    message: string;
    agent: string;
    every_minutes: number | null;
    days: number[];
    at: string;
    enabled: boolean;
    last_run: string | null;
  };
  const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

  let missions = $state<Mission[]>([]);
  let cap = $state(20);
  let error = $state<string | null>(null);
  // False until the first answer (or failure).
  let loaded = $state(false);
  const agents = $derived([
    { id: "hippoherman", name: "Hippoherman (main agent)" },
    ...addedAgents.list
      .filter((a) => !archived.ids.includes(a.id))
      .map((a) => ({ id: a.id, name: a.name })),
  ]);

  // The form.
  let label = $state("");
  let message = $state("");
  let agent = $state("hippoherman");
  let kind = $state<"every" | "weekly">("every");
  let minutes = $state(60);
  let days = $state<number[]>([0]);
  let at = $state("09:00");
  let confirming = $state<string | null>(null);

  async function call(
    method: string,
    params: Record<string, unknown> = {},
  ): Promise<boolean> {
    error = null;
    try {
      const result = await invoke<{ missions: Mission[]; cap: number }>(
        "sidecar_call",
        { method, params },
      );
      missions = result.missions;
      cap = result.cap;
      return true;
    } catch (cause) {
      error = String(cause);
      return false;
    }
  }

  onMount(() => {
    call("missions")
      .catch((cause) => report("Could not read the missions", cause))
      .finally(() => (loaded = true));
  });

  async function add(): Promise<void> {
    const ok = await call("mission_save", {
      mission: {
        label,
        message,
        agent,
        ...(kind === "every"
          ? { every_minutes: Number(minutes) }
          : { days, at }),
      },
    });
    if (ok) {
      label = "";
      message = "";
    }
  }

  function when(m: Mission): string {
    if (m.every_minutes !== null)
      return m.every_minutes % 1440 === 0
        ? `every ${m.every_minutes / 1440} day(s)`
        : m.every_minutes % 60 === 0
          ? `every ${m.every_minutes / 60} hour(s)`
          : `every ${m.every_minutes} minutes`;
    return `${m.days.map((d) => DAYS[d]).join(", ")} at ${m.at}`;
  }

  async function remove(id: string): Promise<void> {
    if (confirming !== id) {
      confirming = id;
      return;
    }
    confirming = null;
    await call("mission_remove", { id });
  }
</script>

<h4>Missions</h4>
<p class="muted">
  A message sent to an agent on a schedule. A new mission starts off; switch it
  on when you want it to run. {missions.length} of {cap} used.
</p>
{#if !loaded}
  <Loading what="the missions" />
{:else if missions.length}
  <ul aria-label="Missions">
    {#each missions as m (m.id)}
      <li>
        <Toggle
          checked={m.enabled}
          label={m.label}
          onchange={(on) =>
            void call("mission_save", { mission: { ...m, enabled: on } })}
        />
        <span class="muted"
          >to {agents.find((a) => a.id === m.agent)?.name ?? m.agent}, {when(
            m,
          )}{m.last_run
            ? `, last sent ${m.last_run.slice(5, 16).replace("T", " ")}`
            : ""}</span
        >
        <Button
          variant="danger"
          size="sm"
          aria-label={confirming === m.id
            ? `Confirm remove ${m.label}`
            : `Remove ${m.label}`}
          onclick={() => void remove(m.id)}
          >{confirming === m.id ? "Confirm remove" : "Remove"}</Button
        >
      </li>
    {/each}
  </ul>
{/if}
<form
  class="add"
  aria-label="New mission"
  onsubmit={(e) => {
    e.preventDefault();
    void add();
  }}
>
  <label>Label <input type="text" bind:value={label} maxlength="60" /></label>
  <label
    >To
    <select bind:value={agent}>
      {#each agents as a (a.id)}<option value={a.id}>{a.name}</option>{/each}
    </select>
  </label>
  <label class="wide"
    >Message <input type="text" bind:value={message} maxlength="2000" /></label
  >
  <label
    >Schedule
    <select bind:value={kind}>
      <option value="every">Every few minutes or hours</option>
      <option value="weekly">On weekdays at a time</option>
    </select>
  </label>
  {#if kind === "every"}
    <label
      >Minutes (15 to 10080)
      <input type="number" min="15" max="10080" bind:value={minutes} /></label
    >
  {:else}
    <fieldset>
      <legend>Days</legend>
      {#each DAYS as day, index (day)}
        <label class="day"
          ><input
            type="checkbox"
            checked={days.includes(index)}
            onchange={(e) =>
              (days = e.currentTarget.checked
                ? [...days, index]
                : days.filter((d) => d !== index))}
          />{day}</label
        >
      {/each}
    </fieldset>
    <label>Time <input type="time" bind:value={at} /></label>
  {/if}
  <Button
    type="submit"
    variant="primary"
    disabled={!label.trim() || !message.trim()}>Add mission</Button
  >
</form>
{#if error}<p class="error" role="alert">{error}</p>{/if}

<style>
  h4 {
    margin: var(--space-3) 0 var(--space-1);
    font-size: var(--font-size-sm);
  }

  ul {
    margin: 0;
    padding-left: var(--space-4);
  }

  li {
    display: flex;
    flex-wrap: wrap;
    align-items: center;
    gap: var(--space-2);
  }

  .add {
    display: flex;
    flex-wrap: wrap;
    align-items: end;
    gap: var(--space-2);
    margin-top: var(--space-2);
  }

  .add label,
  fieldset {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }

  .add .wide {
    flex: 1 1 100%;
  }

  fieldset {
    flex-direction: row;
    flex-wrap: wrap;
    margin: 0;
    padding: var(--space-1) var(--space-2);
    border: 1px solid var(--color-border);
  }

  .add .day {
    flex-direction: row;
    align-items: center;
  }

  .error {
    color: var(--color-danger);
  }
</style>
