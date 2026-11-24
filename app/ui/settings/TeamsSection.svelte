<script lang="ts">
  import { onMount } from "svelte";
  import Button from "../controls/Button.svelte";
  import { call } from "./call";

  // D.07: people who share the same agents, tasks and notes, each with their own sign-in. Built on the Hippocampus
  // account. Nothing moves unless a button is pressed: Save to team uploads, Get from team downloads.
  type Team = { id: string; name: string; role: string; code: string };
  type State = {
    signed_in: boolean;
    configured: boolean;
    teams: Team[];
    members?: { email: string; role: string }[];
    shared?: { agents: string[]; tasks: string[]; notes: string[] };
  };
  let view = $state<State | null>(null);
  let team = $state("");
  let name = $state("");
  let code = $state("");
  let done = $state("");
  let error = $state("");
  let busy = $state(false);

  async function act(fn: () => Promise<void>): Promise<void> {
    busy = true;
    error = "";
    done = "";
    try {
      await fn();
    } catch (cause) {
      error = String(cause);
    } finally {
      busy = false;
    }
  }
  async function load(): Promise<void> {
    view = await call<State>("teams_state", { team });
    if (!view.teams.some((t) => t.id === team)) team = view.teams[0]?.id ?? "";
  }
  async function change(method: string, params: Record<string, unknown>) {
    view = await call<State>(method, params);
    team =
      view.teams.find((t) => t.id === team)?.id ?? view.teams.at(-1)?.id ?? "";
    await load();
  }
  onMount(() => void act(load));
  const current = $derived(view?.teams.find((t) => t.id === team));
</script>

<section class="control-section" aria-labelledby="teams-title">
  <h3 id="teams-title">Teams</h3>
  <p class="hint">
    A team shares agents (name, model and goal, never a folder on your
    computer), task titles, and the notes in your vault's Team folder. Each
    person signs in with their own account. Nothing is shared until you press
    Save to team, and nothing changes here until you press Get from team.
  </p>
  {#if view && !view.signed_in}
    <p class="muted">Sign in under Account to use teams.</p>
  {:else if view}
    <ul aria-label="Your teams">
      {#each view.teams as t (t.id)}
        <li>
          <label>
            <input
              type="radio"
              name="team"
              value={t.id}
              bind:group={team}
              onchange={() => void act(load)}
            />
            {t.name} <span class="muted">({t.role})</span>
          </label>
        </li>
      {:else}
        <li class="muted">You are not in a team yet.</li>
      {/each}
    </ul>
    <form
      class="row"
      onsubmit={(e) => {
        e.preventDefault();
        void act(async () => {
          await change("team_create", { name });
          name = "";
        });
      }}
    >
      <input
        aria-label="Team name"
        placeholder="New team name"
        bind:value={name}
      />
      <Button type="submit" disabled={busy || !name.trim()}>Make a team</Button>
    </form>
    <form
      class="row"
      onsubmit={(e) => {
        e.preventDefault();
        void act(async () => {
          await change("team_join", { code });
          code = "";
        });
      }}
    >
      <input aria-label="Team code" placeholder="Team code" bind:value={code} />
      <Button type="submit" disabled={busy || !code.trim()}>Join a team</Button>
    </form>
    {#if current}
      <h4>{current.name}</h4>
      {#if current.code}
        <p>Give this code to a teammate: <code>{current.code}</code></p>
      {/if}
      <div class="row">
        <Button
          variant="primary"
          disabled={busy}
          onclick={() =>
            void act(async () => {
              const r = await call<{
                agents: number;
                tasks: number;
                notes: number;
              }>("team_save", { team });
              done = `Saved ${r.agents} agents, ${r.tasks} task titles and ${r.notes} notes to the team.`;
              await load();
            })}>Save to team</Button
        >
        <Button
          disabled={busy}
          onclick={() =>
            void act(async () => {
              const r = await call<{
                agents_added: string[];
                notes_written: number;
              }>("team_get", { team });
              done = `Got ${r.agents_added.length} new agents and ${r.notes_written} notes from the team.`;
            })}>Get from team</Button
        >
        {#if current.role !== "owner"}
          <Button
            variant="ghost"
            disabled={busy}
            onclick={() => void act(() => change("team_leave", { team }))}
            >Leave the team</Button
          >
        {/if}
      </div>
      {#if view.members}
        <p class="muted">
          Members: {view.members.map((m) => m.email).join(", ")}
        </p>
      {/if}
      {#if view.shared}
        <p>
          Shared now: {view.shared.agents.length} agents, {view.shared.tasks
            .length}
          tasks, {view.shared.notes.length} notes.
        </p>
        {#if view.shared.tasks.length}
          <ul aria-label="Team tasks">
            {#each view.shared.tasks as task (task)}<li>{task}</li>{/each}
          </ul>
        {/if}
      {/if}
    {/if}
  {/if}
  {#if done}<p role="status">{done}</p>{/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>

<style>
  .row {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    flex-wrap: wrap;
    margin-bottom: var(--space-2);
  }
  input:not([type="radio"]) {
    min-width: 0;
    flex: 1 1 200px;
  }
  ul {
    list-style: none;
    padding: 0;
    margin: 0 0 var(--space-2);
  }
</style>
