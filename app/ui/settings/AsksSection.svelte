<script lang="ts">
  import ErrorRow from "../controls/ErrorRow.svelte";
  import { onChanged } from "../changed.ts";
  import { invoke } from "@tauri-apps/api/core";
  import { onDestroy, onMount } from "svelte";
  import type { AskCard } from "../assistant/model";
  import Loading from "../controls/Loading.svelte";
  import Button from "../controls/Button.svelte";

  // Questions the assistant cannot answer alone, from every chat, in one place.
  let asks = $state<AskCard[]>([]);
  // Tool calls waiting for approval (7.19). Also shown in the chat that made them; either place decides.
  type Approval = { call: string; name: string; preview: string };
  let approvals = $state<Approval[]>([]);
  let answers = $state<Record<string, string>>({});
  let error = $state<string | null>(null);
  // What you answered since the app started, newest first, so an answer can be checked after it is sent.
  let answered = $state<{ question: string; text: string; at: string }[]>([]);
  // False until the first answer (or failure).
  let loaded = $state(false);
  let stopPoll: (() => void) | undefined;

  async function load(): Promise<void> {
    try {
      const result = await invoke<{
        asks: AskCard[];
        approvals?: Approval[];
      }>("sidecar_call", {
        method: "asks",
      });
      asks = result.asks;
      approvals = result.approvals ?? [];
    } catch (cause) {
      error = String(cause);
    } finally {
      loaded = true;
    }
  }

  async function respond(ask: AskCard): Promise<void> {
    const text = (answers[ask.call] ?? "").trim();
    if (!text) return;
    error = null;
    try {
      await invoke("sidecar_call", {
        method: "answer",
        params: { call: ask.call, text },
      });
      answers[ask.call] = "";
      answered = [
        {
          question: ask.question,
          text,
          at: new Date().toTimeString().slice(0, 5),
        },
        ...answered,
      ].slice(0, 20);
      await load();
    } catch (cause) {
      error = String(cause);
    }
  }

  async function decide(row: Approval, approve: boolean): Promise<void> {
    error = null;
    try {
      await invoke("sidecar_call", {
        method: "confirm",
        params: { call: row.call, approve },
      });
      answered = [
        {
          question: `${row.name}: ${row.preview}`,
          text: approve ? "Approved" : "Denied",
          at: new Date().toTimeString().slice(0, 5),
        },
        ...answered,
      ].slice(0, 20);
      await load();
    } catch (cause) {
      error = String(cause);
    }
  }

  onMount(() => {
    void load();
    stopPoll = onChanged("asks", load);
  });
  onDestroy(() => stopPoll?.());
</script>

<section class="control-section" aria-labelledby="control-asks">
  <h3 id="control-asks">Ask me</h3>
  <p class="hint">
    Questions and tool calls the assistant is waiting on. Answer here or in its
    chat.
  </p>
  {#if approvals.length}
    <ul aria-label="Waiting approvals">
      {#each approvals as row (row.call)}
        <li>
          <p><strong>{row.name}</strong> · {row.preview}</p>
          <div class="row">
            <Button variant="primary" onclick={() => decide(row, true)}
              >Approve</Button
            >
            <Button onclick={() => decide(row, false)}>Deny</Button>
          </div>
        </li>
      {/each}
    </ul>
  {/if}
  {#if !loaded}
    <Loading what="the questions" />
  {:else if asks.length === 0}
    {#if approvals.length === 0}
      <p class="muted">Nothing is waiting.</p>
    {/if}
  {:else}
    <ul aria-label="Waiting questions">
      {#each asks as ask (ask.call)}
        <li>
          <p>{ask.question}</p>
          <div class="row">
            <input
              type="text"
              aria-label={`Answer: ${ask.question}`}
              bind:value={answers[ask.call]}
              placeholder="Type your answer, then press Enter"
              onkeydown={(e) => e.key === "Enter" && respond(ask)}
            />
            <Button variant="primary" onclick={() => respond(ask)}
              >Respond</Button
            >
          </div>
        </li>
      {/each}
    </ul>
  {/if}
  {#if answered.length}
    <h4>Answered</h4>
    <ul aria-label="Answered questions">
      {#each answered as row, index (index)}
        <li>
          <p class="muted">{row.at} · {row.question}</p>
          <p>{row.text}</p>
        </li>
      {/each}
    </ul>
  {/if}
  {#if error}<ErrorRow message={error} onretry={load} />{/if}
</section>

<style>
  ul {
    display: grid;
    gap: var(--space-2);
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    padding: var(--space-2) var(--space-3);
    background: var(--color-bg-1);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
  }

  li p {
    margin: 0 0 var(--space-2);
  }

  .row {
    display: flex;
    gap: var(--space-2);
    align-items: center;
  }

  .row input {
    flex: 1;
  }
</style>
