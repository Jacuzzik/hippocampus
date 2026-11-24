<script lang="ts">
  import { onMount } from "svelte";
  import Button from "../controls/Button.svelte";
  import Toggle from "../controls/Toggle.svelte";
  import { addedAgents } from "../owner/addedAgents.svelte.ts";
  import { call } from "./call";

  // 7.25: one Slack bot. The token is kept in the system keychain. The app asks Slack for new messages in the chosen
  // conversations and posts the agent's answer in the thread; nothing listens on a port.
  type State = {
    connected: boolean;
    workspace: string;
    bot: string;
    on: boolean;
    agent: string;
    chosen: string[];
    error: string;
    forwarded: number;
    answered: number;
  };
  type Row = { id: string; name: string; kind: string };
  let view = $state<State | null>(null);
  let rows = $state<Row[]>([]);
  let chosen = $state<string[]>([]);
  let agent = $state("hippoherman");
  let token = $state("");
  let error = $state("");
  let busy = $state(false);

  async function act(fn: () => Promise<void>): Promise<void> {
    busy = true;
    error = "";
    try {
      await fn();
    } catch (cause) {
      error = String(cause);
    } finally {
      busy = false;
    }
  }
  function setView(next: State): void {
    view = next;
    chosen = [...next.chosen];
    agent = next.agent;
  }
  async function listRows(): Promise<void> {
    rows = (await call<{ rows: Row[] }>("slack_conversations")).rows;
  }
  onMount(
    () =>
      void act(async () => {
        setView(await call<State>("slack_state"));
        if (view?.connected) await listRows().catch(() => {});
      }),
  );
  const agents = $derived([
    { id: "hippoherman", name: "Main agent" },
    ...addedAgents.list.map((a) => ({ id: a.id, name: a.name })),
  ]);
  const save = (on: boolean) =>
    act(async () =>
      setView(await call<State>("slack_set", { channels: chosen, agent, on })),
    );
</script>

<section class="control-section" aria-labelledby="slack-title">
  <h3 id="slack-title">Slack bot</h3>
  <p class="hint">
    Make a Slack app with a bot user (scopes: channels:history, groups:history,
    im:history, chat:write, and channels:read, groups:read, im:read to list
    conversations), install it, and paste its bot token (xoxb-…). The token is
    kept in the system keychain. The bot answers only in the conversations you
    choose, forwards each message to one agent, and posts that agent's reply in
    the thread. It needs the network set to Converse or Open.
  </p>
  {#if view && !view.connected}
    <form
      class="row"
      onsubmit={(e) => {
        e.preventDefault();
        void act(async () => {
          setView(await call<State>("slack_connect", { token }));
          token = "";
          await listRows();
        });
      }}
    >
      <input
        aria-label="Slack bot token"
        type="password"
        placeholder="xoxb-…"
        bind:value={token}
      />
      <Button type="submit" variant="primary" disabled={busy || !token.trim()}
        >Connect</Button
      >
    </form>
  {:else if view}
    <p>
      Connected to {view.workspace} as {view.bot}. Forwarded {view.forwarded},
      answered {view.answered}.
    </p>
    <fieldset>
      <legend>Conversations the bot answers in</legend>
      {#each rows as row (row.id)}
        <label class="check">
          <input type="checkbox" value={row.id} bind:group={chosen} />
          {row.name}
        </label>
      {:else}
        <p class="muted">
          The bot is in no channel yet. Invite it with /invite, or send it a
          direct message, then reload the list.
        </p>
      {/each}
    </fieldset>
    <label>
      Agent that answers
      <select bind:value={agent}>
        {#each agents as a (a.id)}<option value={a.id}>{a.name}</option>{/each}
      </select>
    </label>
    <div class="row">
      <Toggle
        ariaLabel="Slack bridge"
        checked={view.on}
        label={view.on ? "On" : "Off"}
        onchange={(on) => void save(on)}
      />
      <Button disabled={busy} onclick={() => void act(listRows)}
        >Reload the list</Button
      >
      <Button disabled={busy} onclick={() => void save(view?.on ?? false)}
        >Save choices</Button
      >
      <Button
        variant="ghost"
        disabled={busy}
        onclick={() =>
          void act(async () => setView(await call<State>("slack_disconnect")))}
        >Disconnect</Button
      >
    </div>
    {#if view.error}<p class="error" role="alert">{view.error}</p>{/if}
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
  input[type="password"] {
    min-width: 0;
    flex: 1 1 200px;
  }
  fieldset {
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    margin: 0 0 var(--space-2);
  }
  .check {
    display: flex;
    gap: var(--space-2);
    align-items: center;
  }
</style>
