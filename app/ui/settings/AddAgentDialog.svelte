<script lang="ts">
  import Dropdown from "../controls/Dropdown.svelte";
  import Dialog from "../controls/Dialog.svelte";
  import AgentCardPreview from "../owner/AgentCardPreview.svelte";
  import { report } from "../notices.svelte.ts";
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import { addAgent } from "../owner/addedAgents.svelte";
  import {
    AGENT_MODELS,
    AGENT_PROVIDERS,
    AUTONOMY_LEVELS,
    AGENT_TEMPLATES,
    AGENT_STEPS,
    AVATARS,
    CARD_FACES,
    providerLogo,
    agentCommand,
    agentStepError,
    engineStatus,
    type AgentDraft,
    type CliState,
  } from "./model";

  // The Add agent dialog: four steps, then Spawn adds the agent to the agent bar.
  let { onclose }: { onclose: () => void } = $props();

  function blankDraft(): AgentDraft {
    return {
      name: "",
      character: CARD_FACES[0]?.id ?? AVATARS[0].id,
      // Empty until the user picks or creates a folder inside the app's workspaces folder.
      folder: "",
      provider: AGENT_PROVIDERS[0].id,
      model: "",
      command: "",
      description: "",
      goal: "",
      autonomy: "edits",
    };
  }

  let step = $state(0);
  let error = $state<string | null>(null);
  let savedKeys = $state<string[]>([]);
  let draft = $state<AgentDraft>(blankDraft());
  // "brain" uses the brain folder; "other" picks one of the folders inside the app's workspaces folder.
  let folderChoice = $state<"brain" | "other">("other");
  let workspaces = $state<{ root: string; folders: string[] }>({
    root: "",
    folders: [],
  });
  let newFolder = $state("");
  let workspaceError = $state<string | null>(null);

  let clis = $state<CliState[]>([]);
  let servers = $state<{ provider: string; running: boolean }[]>([]);
  const engine = $derived(
    engineStatus(draft.provider, savedKeys, clis, servers),
  );
  const custom = $derived(draft.provider === "custom");
  const command = $derived(
    custom || draft.model.trim() !== "" ? agentCommand(draft) : "",
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
      clis = (
        await invoke<{ clis: CliState[] }>("sidecar_call", {
          method: "provider_status",
        })
      ).clis;
    } catch (cause) {
      report("Could not check the CLI logins", cause);
    }
    try {
      servers = (
        await invoke<{ servers: { provider: string; running: boolean }[] }>(
          "sidecar_call",
          { method: "local_status" },
        )
      ).servers;
    } catch (cause) {
      report("Could not check the local model servers", cause);
    }
  }

  // The briefing this agent would start with, built by the backend from the words typed so far.
  let preview = $state<{
    text: string;
    version: number;
    characters: number;
  } | null>(null);
  let previewBusy = $state(false);
  async function previewBriefing(): Promise<void> {
    previewBusy = true;
    try {
      preview = await invoke("sidecar_call", {
        method: "briefing_preview",
        params: {
          name: draft.name,
          description: draft.description,
          goal: draft.goal,
          folder: draft.folder,
        },
      });
    } catch (cause) {
      report("Could not build the briefing preview", cause);
    } finally {
      previewBusy = false;
    }
  }

  function next(): void {
    error = agentStepError(step, draft);
    if (!error) step += 1;
  }

  async function loadWorkspaces(): Promise<void> {
    try {
      workspaces = await invoke<{ root: string; folders: string[] }>(
        "sidecar_call",
        { method: "workspaces" },
      );
    } catch (cause) {
      report("Could not list the workspaces", cause);
    }
  }

  let folderBusy = $state(false);
  async function createWorkspace(): Promise<void> {
    const name = newFolder.trim();
    workspaceError = null;
    folderBusy = true;
    try {
      workspaces = await invoke<{ root: string; folders: string[] }>(
        "sidecar_call",
        {
          method: "create_workspace",
          params: { name },
        },
      );
      newFolder = "";
      chooseFolder("other", name);
    } catch (cause) {
      workspaceError = String(cause);
    } finally {
      folderBusy = false;
    }
  }

  function chooseFolder(choice: "brain" | "other", name?: string): void {
    folderChoice = choice;
    if (choice === "brain") draft.folder = ".";
    else draft.folder = name ? `${workspaces.root}/${name}` : "";
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

  onMount(() => {
    void loadKeys();
    void loadWorkspaces();
  });
</script>

<Dialog
  title="Add agent"
  {onclose}
  closeLabel="Close add agent"
  center
  dim
  z={50}
  width="min(32rem, calc(100vw - 2 * var(--space-4)))"
>
  <!-- The agent card as the bottom bar draws it, filled in as each step is answered. -->
  <AgentCardPreview
    name={draft.name.trim()}
    face={CARD_FACES.find((f) => f.id === draft.character)?.url ?? ""}
    provider={AGENT_PROVIDERS.find((p) => p.id === draft.provider)?.label ?? ""}
    logo={providerLogo(draft.provider)}
    model={draft.model.trim()}
    cmd={command}
  />
  <div class="progress" aria-hidden="true">
    {#each AGENT_STEPS as label, i (label)}
      <span class:done={i <= step}></span>
    {/each}
  </div>
  <p class="stepname" role="status">
    Step {step + 1} of {AGENT_STEPS.length} · {AGENT_STEPS[step]}
  </p>

  {#if step === 0}
    <label>Name <input type="text" bind:value={draft.name} /></label>
    <fieldset class="picker">
      <legend>Avatar</legend>
      <div class="faces">
        {#each CARD_FACES as face (face.id)}
          <button
            type="button"
            class="face-pick"
            aria-label={face.id}
            aria-pressed={draft.character === face.id}
            class:on={draft.character === face.id}
            onclick={() => (draft.character = face.id)}
          >
            <img src={face.url} alt="" />
          </button>
        {/each}
      </div>
    </fieldset>
  {:else if step === 1}
    <div class="choice" role="radiogroup" aria-label="Folder">
      <button
        type="button"
        role="radio"
        aria-checked={folderChoice === "other"}
        class:on={folderChoice === "other"}
        onclick={() => chooseFolder("other")}>Workspaces folder</button
      >
    </div>
    {#if folderChoice === "other"}
      {#if workspaces.folders.length > 0}
        <label
          >Folder in workspaces
          <select
            onchange={(e) => chooseFolder("other", e.currentTarget.value)}
          >
            <option value="">Choose a folder</option>
            {#each workspaces.folders as name (name)}
              <option
                value={name}
                selected={draft.folder === `${workspaces.root}/${name}`}
                >{name}</option
              >
            {/each}
          </select>
        </label>
      {/if}
      <label>
        New folder inside workspaces
        <input type="text" bind:value={newFolder} placeholder="Folder name" />
      </label>
      <div class="choice">
        <button
          type="button"
          disabled={!newFolder.trim() || folderBusy}
          onclick={createWorkspace}>Create folder</button
        >
      </div>
      {#if workspaceError}<p class="error" role="alert">
          {workspaceError}
        </p>{/if}
    {/if}
  {:else if step === 2}
    <div class="field">
      <span>Provider</span>
      <Dropdown
        label="Provider"
        bind:value={draft.provider}
        options={AGENT_PROVIDERS.map((p) => ({
          value: p.id,
          label: p.label,
        }))}
        onchange={() => (draft.model = "")}
      />
    </div>
    {#if custom}
      <label
        >Command <input
          type="text"
          bind:value={draft.command}
          placeholder="e.g. aider --model sonnet"
        /></label
      >
    {:else}
      <label
        >Model <input
          type="text"
          readonly
          value={draft.model}
          placeholder="Pick a model below"
        /></label
      >
      <div class="choice" aria-label="Suggested models">
        {#each AGENT_MODELS[draft.provider] ?? [] as m (m)}
          <button
            type="button"
            class:on={draft.model === m}
            onclick={() => (draft.model = m)}>{m}</button
          >
        {/each}
      </div>
    {/if}
    <p class="command">
      <span class="muted">Command</span>
      <code
        >{command ||
          (custom
            ? "Type a command to run."
            : "Pick a model to see the command.")}</code
      >
    </p>
    <fieldset class="picker">
      <legend>Autonomy</legend>
      <div class="choice" role="radiogroup" aria-label="Autonomy">
        {#each AUTONOMY_LEVELS as level (level.id)}
          <button
            type="button"
            role="radio"
            aria-checked={draft.autonomy === level.id}
            class:on={draft.autonomy === level.id}
            title={level.hint}
            onclick={() => (draft.autonomy = level.id)}>{level.label}</button
          >
        {/each}
      </div>
      <p class="muted">
        {AUTONOMY_LEVELS.find((l) => l.id === draft.autonomy)?.hint}
      </p>
    </fieldset>
    <p class={engine.ready ? "muted" : "error"} role="status">
      {engine.text}
    </p>
  {:else}
    <div class="choice" aria-label="Job">
      {#each AGENT_TEMPLATES as t (t.id)}
        <button
          type="button"
          class:on={draft.description === t.description}
          onclick={() => {
            draft.description = t.description;
            draft.goal = t.goal;
          }}>{t.label}</button
        >
      {/each}
    </div>
    <label
      >Description
      <textarea
        rows="3"
        maxlength="100"
        bind:value={draft.description}
        placeholder="What should this agent do? Pick a premade above or write your own."
      ></textarea>
    </label>
    <p class="muted count">{draft.description.length} / 100</p>
    <label
      >Goal
      <textarea
        rows="3"
        maxlength="4000"
        bind:value={draft.goal}
        placeholder="The outcome this agent is working toward."></textarea>
    </label>
    <p class="muted count">{draft.goal.length} / 4000</p>
    <button
      type="button"
      disabled={previewBusy}
      onclick={() => void previewBriefing()}>Preview briefing</button
    >
    {#if preview}
      <p class="muted">
        Briefing v{preview.version}, {preview.characters} characters. Two sections
        are added when the agent starts: its start-up inbox and the limits in force.
      </p>
      <pre class="preview" aria-label="Briefing preview">{preview.text}</pre>
    {/if}
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
</Dialog>

<style>
  .face-pick {
    padding: 0;
    background: none;
    border: 0;
    cursor: pointer;
  }

  .face-pick img {
    display: block;
    width: var(--size-48);
    height: var(--size-48);
    border-radius: 50%;
  }

  /* The selected avatar gets a square ring with a gap between it and the picture. */
  .face-pick.on {
    outline: 2px solid var(--color-accent);
    outline-offset: 3px;
  }

  .choice {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
    margin-top: var(--space-2);
  }

  .choice button {
    font: inherit;
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
    background: var(--color-bg-0);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    padding: var(--space-1) var(--space-2);
    cursor: pointer;
  }

  .choice button.on,
  .choice button[aria-checked="true"] {
    color: var(--color-text);
    border-color: var(--color-accent);
  }

  .muted {
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }

  .count {
    text-align: right;
    margin: 0;
  }

  .progress {
    display: flex;
    gap: var(--space-1);
    margin: var(--space-2) 0 0;
  }

  .progress span {
    flex: 1;
    height: 4px;
    border-radius: 2px;
    background: var(--color-border);
  }

  .progress span.done {
    background: var(--color-accent);
  }

  .stepname {
    margin: var(--space-1) 0 0;
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }

  label,
  .field,
  .picker {
    display: block;
    margin-top: var(--space-2);
    color: var(--color-text-muted);
  }

  .picker {
    border: 0;
    padding: 0;
  }

  .faces {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
    margin-top: var(--space-2);
    padding: var(--space-1);
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
    padding: var(--space-1) var(--space-2);
    color: var(--color-text);
    background: var(--color-bg-0);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    font: inherit;
  }

  label input[type="text"]:focus,
  label select:focus,
  label textarea:focus {
    outline: none;
    border-color: var(--color-accent);
  }

  label select option {
    color: var(--color-text);
    background: var(--color-surface);
  }

  .command {
    display: grid;
    gap: var(--space-1);
  }

  .command code {
    overflow-wrap: anywhere;
  }

  .row {
    display: flex;
    justify-content: flex-end;
    gap: var(--space-2);
    margin-top: var(--space-4);
  }

  .row button {
    font: inherit;
    font-size: var(--font-size-sm);
    color: var(--color-text);
    background: var(--color-bg-0);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    padding: var(--space-1) var(--space-3);
    cursor: pointer;
  }

  .row button:hover:not(:disabled) {
    border-color: var(--color-accent);
  }

  .row button:disabled {
    opacity: 0.4;
    cursor: default;
  }

  .row button.primary {
    color: var(--color-accent-on);
    background: var(--color-accent);
    border-color: var(--color-accent);
  }

  .preview {
    max-height: 16em;
    overflow: auto;
    margin: 0;
    padding: var(--space-2);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    white-space: pre-wrap;
    font-size: var(--font-size-xs);
  }
</style>
