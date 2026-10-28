<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import { FACES } from "../assistant/agentCard";
  import {
    AGENT_PROVIDERS,
    AGENT_STEPS,
    agentStepError,
    engineStatus,
    type AgentDraft,
  } from "./model";

  // A four-step form for a new agent. Creating one needs agent storage, which is not set up yet.
  const COLOURS = ["accent", "think", "confirm", "danger"];
  const ISOLATION = [
    { id: "shared", label: "Shared folder" },
    { id: "own", label: "Its own copy of the folder" },
  ] as const;

  let step = $state(0);
  let error = $state<string | null>(null);
  let savedKeys = $state<string[]>([]);
  let draft = $state<AgentDraft>({
    name: "",
    character: FACES[0],
    colour: "accent",
    folder: "",
    isolation: "shared",
    resume: true,
    provider: "claude",
    model: "",
    command: "",
    description: "",
    goal: "",
  });

  const engine = $derived(engineStatus(draft.provider, savedKeys));

  async function loadKeys(): Promise<void> {
    try {
      const result = await invoke<{
        keys: { provider: string; saved: boolean }[];
      }>("sidecar_call", { method: "keys" });
      savedKeys = result.keys.filter((k) => k.saved).map((k) => k.provider);
    } catch (cause) {
      error = String(cause);
    }
  }

  function next(): void {
    error = agentStepError(step, draft);
    if (!error) step += 1;
  }

  onMount(() => void loadKeys());
</script>

<section class="control-section" aria-labelledby="control-add-agent">
  <h3 id="control-add-agent">Add an agent</h3>
  <ol class="steps" aria-label="Steps">
    {#each AGENT_STEPS as label, i (label)}
      <li aria-current={i === step ? "step" : undefined} class:done={i < step}>
        {i + 1}. {label}
      </li>
    {/each}
  </ol>

  {#if step === 0}
    <label>Name <input type="text" bind:value={draft.name} /></label>
    <label>
      Character
      <select bind:value={draft.character}>
        {#each FACES as face, i (face)}
          <option value={face}>Character {i + 1}</option>
        {/each}
      </select>
    </label>
    <label>
      Colour
      <select bind:value={draft.colour}>
        {#each COLOURS as colour (colour)}
          <option value={colour}>{colour}</option>
        {/each}
      </select>
    </label>
  {:else if step === 1}
    <label
      >Folder <input
        type="text"
        bind:value={draft.folder}
        placeholder="/path/to/folder"
      /></label
    >
    <label>
      Isolation
      <select bind:value={draft.isolation}>
        {#each ISOLATION as option (option.id)}
          <option value={option.id}>{option.label}</option>
        {/each}
      </select>
    </label>
    <label class="check"
      ><input type="checkbox" bind:checked={draft.resume} /> Resume the last session</label
    >
  {:else if step === 2}
    <label>
      Provider
      <select bind:value={draft.provider}>
        {#each AGENT_PROVIDERS as p (p.id)}
          <option value={p.id}>{p.label}</option>
        {/each}
      </select>
    </label>
    <label>Model <input type="text" bind:value={draft.model} /></label>
    <label
      >Command <input
        type="text"
        bind:value={draft.command}
        placeholder="optional"
      /></label
    >
    <p class={engine.ready ? "muted" : "error"} role="status">{engine.text}</p>
  {:else}
    <label
      >What it does <textarea rows="2" bind:value={draft.description}
      ></textarea></label
    >
    <label>Goal <textarea rows="2" bind:value={draft.goal}></textarea></label>
  {/if}

  <div class="row">
    <button type="button" disabled={step === 0} onclick={() => (step -= 1)}
      >Back</button
    >
    {#if step < AGENT_STEPS.length - 1}
      <button type="button" class="primary" onclick={next}>Next</button>
    {:else}
      <button type="button" disabled>Create agent: Not set up</button>
    {/if}
  </div>
  {#if step === AGENT_STEPS.length - 1}
    <p class="muted">
      Agents are not stored yet, so this form cannot create one.
    </p>
  {/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>

<style>
  .steps {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin: 0 0 var(--space-2);
    padding: 0;
    list-style: none;
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }

  .steps li[aria-current="step"] {
    color: var(--color-text);
    font-weight: 600;
  }

  .steps li.done {
    color: var(--color-text-subtle);
  }

  label {
    display: block;
    margin-top: var(--space-2);
    color: var(--color-text-muted);
  }

  label input[type="text"],
  label select,
  label textarea {
    display: block;
    width: 100%;
    margin-top: var(--space-1);
    box-sizing: border-box;
  }

  label.check input {
    margin-right: var(--space-2);
  }

  label select {
    padding: var(--space-1);
    color: var(--color-text);
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
  }
</style>
