<script lang="ts">
  import Button from "../controls/Button.svelte";
  import { invoke } from "@tauri-apps/api/core";
  import { dispatchError } from "./model";

  // Sends a task to an agent. Nothing is sent until you confirm the exact task shown.
  const AGENTS = [{ id: "helper", label: "Helper", ready: true }];

  let agent = $state("helper");
  let task = $state("");
  // 8.05: the other three parts of the contract. Left empty, the backend fills a plain default.
  let output = $state("");
  let tools = $state("");
  let boundaries = $state("");
  type Pending = {
    agent: string;
    task: string;
    output: string;
    tools: string;
    boundaries: string;
  };
  let pending = $state<Pending | null>(null);
  let sent = $state<string | null>(null);
  let error = $state<string | null>(null);

  function review(): void {
    error = dispatchError(agent, task);
    sent = null;
    if (!error)
      pending = {
        agent,
        task: task.trim(),
        output: output.trim(),
        tools: tools.trim(),
        boundaries: boundaries.trim(),
      };
  }

  // True while the send runs (13.03).
  let sending = $state(false);
  async function confirm(): Promise<void> {
    if (!pending) return;
    const { agent: who, task: text } = pending;
    const parts = {
      objective: text,
      output: pending.output,
      tools: pending.tools,
      boundaries: pending.boundaries,
    };
    pending = null;
    sending = true;
    try {
      await invoke("sidecar_call", {
        method: "start_helper",
        params: { parts },
      });
      sent = `Sent to ${who}.`;
      task = output = tools = boundaries = "";
    } catch (cause) {
      error = String(cause);
    } finally {
      sending = false;
    }
  }
</script>

<section class="control-section" aria-labelledby="control-dispatch">
  <h3 id="control-dispatch">Dispatch</h3>
  <p class="hint">
    Pick an agent and write a task. It goes out in four parts: objective,
    output, tools and boundaries; an empty part gets a plain default. It is sent
    only after you confirm.
  </p>
  <label>
    Agent
    <select bind:value={agent} disabled={pending !== null}>
      {#each AGENTS as option (option.id)}
        <option value={option.id} disabled={!option.ready}
          >{option.label}</option
        >
      {/each}
    </select>
  </label>
  <label class="block">
    Task
    <textarea rows="3" bind:value={task} disabled={pending !== null}></textarea>
  </label>
  <label class="block"
    >Output <input
      type="text"
      bind:value={output}
      placeholder="What to hand back"
      disabled={pending !== null}
    /></label
  >
  <label class="block"
    >Tools <input
      type="text"
      bind:value={tools}
      placeholder="What to use or avoid"
      disabled={pending !== null}
    /></label
  >
  <label class="block"
    >Boundaries <input
      type="text"
      bind:value={boundaries}
      placeholder="Scope and when it is done"
      disabled={pending !== null}
    /></label
  >
  {#if pending}
    <div class="confirm" role="alertdialog" aria-label="Confirm dispatch">
      <p>Send this task to {pending.agent}?</p>
      <p class="task">{pending.task}</p>
      <dl class="parts">
        <dt>Output</dt>
        <dd>{pending.output || "Default: a short reply"}</dd>
        <dt>Tools</dt>
        <dd>{pending.tools || "Default: whatever the agent's rules allow"}</dd>
        <dt>Boundaries</dt>
        <dd>{pending.boundaries || "Default: only this task"}</dd>
      </dl>
      <div class="row">
        <Button onclick={() => (pending = null)}>Cancel</Button>
        <Button variant="primary" onclick={confirm}>Send</Button>
      </div>
    </div>
  {:else}
    <div class="row">
      <Button variant="primary" disabled={sending} onclick={review}
        >{sending ? "Sending…" : "Review and send"}</Button
      >
      {#if sent}<span class="muted">{sent}</span>{/if}
    </div>
  {/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>

<style>
  label {
    display: block;
    margin-top: var(--space-2);
    color: var(--color-text-muted);
  }

  select {
    margin-left: var(--space-2);
    padding: var(--space-1);
    color: var(--color-text);
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
  }

  .parts {
    display: grid;
    grid-template-columns: auto 1fr;
    gap: var(--space-1) var(--space-2);
    margin: var(--space-2) 0;
    font-size: var(--font-size-sm);
  }

  .parts dt {
    color: var(--color-text-muted);
  }

  .parts dd {
    margin: 0;
  }

  .block input,
  .block textarea {
    display: block;
    margin-top: var(--space-1);
  }

  .confirm {
    margin-top: var(--space-2);
    padding: var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
  }

  .confirm p {
    margin: 0 0 var(--space-2);
  }

  .task {
    white-space: pre-wrap;
    color: var(--color-text-muted);
  }
</style>
