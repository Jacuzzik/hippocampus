<script lang="ts">
  import { onMount } from "svelte";
  import Toggle from "../controls/Toggle.svelte";
  import { call } from "./call";

  // N.05: the exact briefing an agent starts with, block by block, with its size. N.04: each agent's trail notes.
  type Block = {
    id: string;
    title: string;
    size: number;
    optional: boolean;
    on: boolean;
  };
  type Preview = {
    text: string;
    size: number;
    limit: number;
    blocks: Block[];
    problems: string[];
    version: number;
    hash: string;
  };
  type Trail = {
    agent: string;
    newest: string;
    path: string;
    recent: boolean;
    count: number;
  };
  let agents = $state<{ id: string; name: string }[]>([]);
  let chosen = $state("hippoherman");
  let preview = $state<Preview | null>(null);
  let trails = $state<Trail[]>([]);
  let error = $state("");

  async function show(
    params: Record<string, unknown> = {},
    method = "briefing_build",
  ): Promise<void> {
    error = "";
    try {
      preview = await call<Preview>(method, { agent: chosen, ...params });
    } catch (cause) {
      error = String(cause);
    }
  }
  onMount(async () => {
    try {
      agents =
        (await call<{ agents: { id: string; name: string }[] }>("agents"))
          .agents ?? [];
      trails = (await call<{ rows: Trail[] }>("trail_notes")).rows ?? [];
    } catch (cause) {
      error = String(cause);
    }
    await show();
  });
  const name = (id: string): string =>
    agents.find((a) => a.id === id)?.name ?? id;
</script>

<section class="control-section" aria-labelledby="briefing-title">
  <h3 id="briefing-title">Briefing builder</h3>
  <p class="hint">
    The exact text an agent gets when it starts, block by block, and its size.
    Optional blocks can be left out for every agent. The rules and the limits in
    force are always sent.
  </p>
  <label class="row"
    >Agent
    <select
      bind:value={chosen}
      aria-label="Agent to preview"
      onchange={() => void show()}
    >
      <option value="hippoherman">Main agent</option>
      {#each agents as agent (agent.id)}<option value={agent.id}
          >{agent.name}</option
        >{/each}
    </select>
  </label>
  {#if preview}
    <p role="status" class:error={preview.size > preview.limit}>
      {preview.size.toLocaleString()} of {preview.limit.toLocaleString()} characters
      (about {Math.round(preview.size / 4).toLocaleString()} tokens) · v{preview.version}
      · {preview.hash}
    </p>
    <ul aria-label="Briefing blocks" class="blocks">
      {#each preview.blocks as block (block.id)}
        <li>
          <span>{block.title}</span>
          <span class="muted">{block.size.toLocaleString()} characters</span>
          {#if block.optional}
            <Toggle
              ariaLabel={`Send ${block.title}`}
              checked={block.on}
              label={block.on ? "Sent" : "Left out"}
              onchange={(on) =>
                void show({ block: block.id, on }, "briefing_blocks_set")}
            />
          {:else}
            <span class="muted">Always sent</span>
          {/if}
        </li>
      {/each}
    </ul>
    {#each preview.problems as problem (problem)}<p class="error" role="alert">
        {problem}
      </p>{/each}
    <details>
      <summary>Show the full text</summary>
      <pre class="text" aria-label="Briefing text">{preview.text}</pre>
    </details>
  {/if}
  <h4>Trail notes</h4>
  <p class="hint">
    Each agent writes a short note in the vault's Trails folder when a session
    ends: what it read, changed and decided.
  </p>
  {#if trails.length === 0}
    <p class="muted">No added agents yet.</p>
  {:else}
    <ul aria-label="Trail notes">
      {#each trails as row (row.agent)}
        <li>
          {name(row.agent)}:
          {#if row.newest}{row.path}{#if !row.recent}<span class="muted">
                (older than a week)</span
              >{/if}
          {:else}<span class="muted">none yet</span>{/if}
        </li>
      {/each}
    </ul>
  {/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>

<style>
  .row,
  .blocks li {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    flex-wrap: wrap;
  }
  .text {
    white-space: pre-wrap;
    max-height: 360px;
    overflow: auto;
    font-size: var(--font-size-sm, 0.85rem);
  }
</style>
