<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { dispatchError } from "./model";

  // Sends a task to an agent. Nothing is sent until you confirm the exact task shown.
  const AGENTS = [
    { id: "helper", label: "Helper", ready: true },
    { id: "assistant", label: "Assistant (Not set up)", ready: false },
  ];

  let agent = $state("helper");
  let task = $state("");
  let pending = $state<{ agent: string; task: string } | null>(null);
  let sent = $state<string | null>(null);
  let error = $state<string | null>(null);

  function review(): void {
    error = dispatchError(agent, task);
    sent = null;
    if (!error) pending = { agent, task: task.trim() };
  }

  async function confirm(): Promise<void> {
    if (!pending) return;
    const { agent: who, task: text } = pending;
    pending = null;
    try {
      await invoke("sidecar_call", {
        method: "start_helper",
        params: { prompt: text },
      });
      sent = `Sent to ${who}.`;
      task = "";
    } catch (cause) {
      error = String(cause);
    }
  }
</script>

<section class="control-section" aria-labelledby="control-dispatch">
  <h3 id="control-dispatch">Dispatch</h3>
  <p class="hint">
    Pick an agent and write a task. It is sent only after you confirm.
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
  {#if pending}
    <div class="confirm" role="alertdialog" aria-label="Confirm dispatch">
      <p>Send this task to {pending.agent}?</p>
      <p class="task">{pending.task}</p>
      <div class="row">
        <button type="button" class="primary" onclick={confirm}>Send</button>
        <button type="button" onclick={() => (pending = null)}>Cancel</button>
      </div>
    </div>
  {:else}
    <div class="row">
      <button type="button" class="primary" onclick={review}
        >Review and send</button
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
