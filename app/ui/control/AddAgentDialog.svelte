<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import { addAgent } from "../owner/addedAgents.svelte";
  import {
    AGENT_COLOURS,
    AGENT_MODELS,
    AGENT_PROVIDERS,
    AGENT_STEPS,
    AGENT_TEMPLATES,
    AVATARS,
    agentCommand,
    agentStepError,
    engineStatus,
    type AgentDraft,
    type CliState,
  } from "./model";

  // The Add agent dialog: four steps, then Spawn adds the agent to the agent bar.
  let { onclose }: { onclose: () => void } = $props();

  const ISOLATION = [
    { id: "shared", label: "Shared folder" },
    { id: "own", label: "Its own git worktree" },
  ] as const;

  function blankDraft(): AgentDraft {
    return {
      name: "",
      character: AVATARS[0].id,
      colour: AGENT_COLOURS[0],
      folder: "",
      isolation: "shared",
      resume: true,
      provider: AGENT_PROVIDERS[0].id,
      model: "",
      command: "",
      autonomy: "ask",
      description: "",
      goal: "",
    };
  }

  let step = $state(0);
  let error = $state<string | null>(null);
  let savedKeys = $state<string[]>([]);
  let draft = $state<AgentDraft>(blankDraft());

  let clis = $state<CliState[]>([]);
  const engine = $derived(engineStatus(draft.provider, savedKeys, clis));
  const command = $derived(
    draft.model.trim() === "" ? "" : agentCommand(draft),
  );

  async function loadKeys(): Promise<void> {
    try {
      const result = await invoke<{
        keys: { provider: string; saved: boolean }[];
      }>("sidecar_call", { method: "keys" });
      savedKeys = result.keys.filter((k) => k.saved).map((k) => k.provider);
    } catch (cause) {
      error = String(cause);
    }
    try {
      clis = (await invoke<{ clis: CliState[] }>("sidecar_call", { method: "provider_status" })).clis;
    } catch (cause) {
      console.error("Could not check the CLI logins", cause);
    }
  }

  function next(): void {
    error = agentStepError(step, draft);
    if (!error) step += 1;
  }

  function useTemplate(id: string): void {
    const template = AGENT_TEMPLATES.find((t) => t.id === id);
    if (!template) return;
    draft.description = template.description;
    draft.goal = template.goal;
    error = null;
  }

  // Checks every step again, so Spawn goes back to the first step with a problem.
  function spawn(): void {
    for (let i = 0; i < AGENT_STEPS.length; i++) {
      error = agentStepError(i, draft);
      if (error) {
        step = i;
        return;
      }
    }
    addAgent({ ...draft, command: agentCommand(draft) });
    onclose();
  }

  // Stops here so the graph's own Escape (which clears the selection) does not also run.
  function onKey(e: KeyboardEvent): void {
    if (e.key === "Escape") {
      e.stopPropagation();
      onclose();
    }
  }

  onMount(() => void loadKeys());
</script>

<div class="scrim" role="presentation" onmousedown={onclose}>
  <div
    class="box"
    role="dialog"
    aria-modal="true"
    aria-labelledby="add-agent-title"
    tabindex="-1"
    onkeydown={onKey}
    onmousedown={(e) => e.stopPropagation()}
  >
    <header>
      <h2 id="add-agent-title">Add agent</h2>
      <button
        type="button"
        class="close"
        aria-label="Close add agent"
        onclick={onclose}>×</button
      >
    </header>

    <ol class="steps" aria-label="Steps">
      {#each AGENT_STEPS as label, i (label)}
        <li
          aria-current={i === step ? "step" : undefined}
          class:done={i < step}
        >
          {i + 1}. {label}
        </li>
      {/each}
    </ol>

    {#if step === 0}
      <label>Name <input type="text" bind:value={draft.name} /></label>
      <fieldset class="picker">
        <legend>Character</legend>
        {#each AVATARS as avatar (avatar.id)}
          <button
            type="button"
            class="avatar"
            aria-label={avatar.name}
            aria-pressed={draft.character === avatar.id}
            onclick={() => (draft.character = avatar.id)}
          >
            <svg
              viewBox="0 0 8 8"
              width="32"
              height="32"
              shape-rendering="crispEdges"
              aria-hidden="true"
            >
              {#each avatar.rows as row, y (y)}
                {#each [...row] as cell, x (x)}
                  {#if cell === "#"}<rect
                      {x}
                      {y}
                      width="1"
                      height="1"
                      fill="currentColor"
                    />{/if}
                {/each}
              {/each}
            </svg>
          </button>
        {/each}
      </fieldset>
      <fieldset class="picker">
        <legend>Colour</legend>
        {#each AGENT_COLOURS as colour (colour)}
          <button
            type="button"
            class="swatch"
            aria-label={colour}
            aria-pressed={draft.colour === colour}
            style:background={`var(--color-${colour})`}
            onclick={() => (draft.colour = colour)}
          ></button>
        {/each}
      </fieldset>
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
      <label>Model <input type="text" list="model-suggestions" bind:value={draft.model} /></label>
      <datalist id="model-suggestions">
        {#each AGENT_MODELS[draft.provider] ?? [] as m (m)}
          <option value={m}></option>
        {/each}
      </datalist>
      <label>
        Autonomy
        <select bind:value={draft.autonomy}>
          <option value="ask">Ask before acting</option>
          <option value="auto">Act on its own within its goal</option>
        </select>
      </label>
      <p class="command">
        <span class="muted">Command</span>
        <code>{command || "Type a model to see the command."}</code>
      </p>
      <p class={engine.ready ? "muted" : "error"} role="status">
        {engine.text}
      </p>
    {:else}
      <div class="templates" role="group" aria-label="Templates">
        {#each AGENT_TEMPLATES as t (t.id)}
          <button type="button" onclick={() => useTemplate(t.id)}
            >{t.label}</button
          >
        {/each}
      </div>
      <label
        >Description <textarea rows="2" bind:value={draft.description}
        ></textarea></label
      >
      <label>Goal <textarea rows="2" bind:value={draft.goal}></textarea></label>
    {/if}

    {#if error}<p class="error" role="alert">{error}</p>{/if}

    <div class="row">
      <button type="button" disabled={step === 0} onclick={() => (step -= 1)}
        >Back</button
      >
      <button type="button" onclick={onclose}>Cancel</button>
      {#if step < AGENT_STEPS.length - 1}
        <button type="button" class="primary" onclick={next}>Next</button>
      {:else}
        <button type="button" class="primary" onclick={spawn}>Spawn</button>
      {/if}
    </div>
  </div>
</div>

<style>
  .scrim {
    position: fixed;
    inset: 0;
    z-index: 50;
    display: grid;
    place-items: center;
    background: color-mix(in srgb, var(--color-bg-0) 70%, transparent);
  }

  .box {
    width: min(32rem, calc(100vw - 2 * var(--space-4)));
    max-height: calc(100vh - 2 * var(--space-4));
    overflow-y: auto;
    padding: var(--space-4);
    color: var(--color-text);
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    box-sizing: border-box;
  }

  header {
    display: flex;
    align-items: center;
    justify-content: space-between;
  }

  h2 {
    margin: 0;
    font-size: var(--font-size-md);
  }

  .steps {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    margin: var(--space-2) 0;
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

  label,
  .picker {
    display: block;
    margin-top: var(--space-2);
    color: var(--color-text-muted);
  }

  .picker {
    border: 0;
    padding: 0;
  }

  .picker legend {
    padding: 0;
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

  .avatar,
  .swatch {
    margin: var(--space-1) var(--space-1) 0 0;
    padding: var(--space-1);
    color: var(--color-text);
    background: transparent;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
  }

  .avatar[aria-pressed="true"],
  .swatch[aria-pressed="true"] {
    border-color: var(--color-text);
  }

  .swatch {
    width: 2rem;
    height: 2rem;
  }

  .command {
    display: grid;
    gap: var(--space-1);
  }

  .command code {
    overflow-wrap: anywhere;
  }

  .templates {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
    margin-top: var(--space-2);
  }

  .row {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-2);
    margin-top: var(--space-4);
  }
</style>
