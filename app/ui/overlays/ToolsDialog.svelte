<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import { allowlistAfter, type ToolRow } from "./allowlist";

  // Which tools the assistant may use. Each change is saved at once; the settings file keeps it.
  let { onclose }: { onclose: () => void } = $props();

  let tools = $state<ToolRow[]>([]);
  let every = $state(true);
  let error = $state<string | null>(null);

  async function load(): Promise<void> {
    try {
      const result = await invoke<{ tools: ToolRow[]; every: boolean }>(
        "sidecar_call",
        { method: "tools" },
      );
      tools = result.tools;
      every = result.every;
    } catch (cause) {
      error = String(cause);
    }
  }

  async function save(names: string[] | null): Promise<void> {
    error = null;
    try {
      await invoke("sidecar_call", { method: "set_tools", params: { names } });
    } catch (cause) {
      error = String(cause);
      await load();
    }
  }

  function toggle(name: string, on: boolean): void {
    const names = allowlistAfter(tools, name, on);
    tools = tools.map((tool) =>
      tool.name === name ? { ...tool, allowed: on } : tool,
    );
    void save(names);
  }

  function toggleEvery(on: boolean): void {
    every = on;
    if (on) {
      void save(null);
      return;
    }
    tools = tools.map((tool) => ({ ...tool, allowed: true }));
    void save(tools.map((tool) => tool.name));
  }

  function onKey(e: KeyboardEvent): void {
    // Stops here so the graph's own Escape (which clears the selection) does not also run.
    if (e.key === "Escape") {
      e.stopPropagation();
      onclose();
    }
  }

  onMount(() => {
    void load();
  });
</script>

<div class="scrim" role="presentation" onmousedown={onclose}>
  <div
    class="box"
    role="dialog"
    aria-modal="true"
    aria-label="Assistant tools"
    tabindex="-1"
    onkeydown={onKey}
    onmousedown={(e) => e.stopPropagation()}
  >
    <h2>Assistant tools</h2>
    <p class="muted">
      Tools the assistant may use. A tool left unticked is refused, even when
      asked.
    </p>

    <label class="every">
      <input
        type="checkbox"
        checked={every}
        onchange={(e) => toggleEvery(e.currentTarget.checked)}
      />
      Every tool
    </label>

    {#if tools.length === 0}
      <p class="muted">Open a brain folder to see the assistant's tools.</p>
    {:else}
      <ul>
        {#each tools as tool (tool.name)}
          <li>
            <label>
              <input
                type="checkbox"
                checked={tool.allowed}
                disabled={every}
                onchange={(e) => toggle(tool.name, e.currentTarget.checked)}
              />
              <span class="name">{tool.name}</span>
              <span class="tier">{tool.tier}</span>
            </label>
          </li>
        {/each}
      </ul>
    {/if}

    {#if error}
      <p role="alert" class="error">{error}</p>
    {/if}
  </div>
</div>

<style>
  .scrim {
    position: fixed;
    inset: 0;
    z-index: 10;
    display: flex;
    justify-content: center;
    align-items: flex-start;
    padding-top: 12vh;
  }

  .box {
    display: flex;
    flex-direction: column;
    gap: var(--space-3);
    width: min(560px, 90vw);
    padding: var(--space-3);
    background: var(--color-bg-1);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    color: var(--color-text);
  }

  h2 {
    margin: 0;
    font-size: var(--font-size-sm);
  }

  p {
    margin: 0;
  }

  .muted {
    color: var(--color-text-muted);
  }

  .every,
  li label {
    display: flex;
    align-items: center;
    gap: var(--space-2);
  }

  .every {
    font-weight: 600;
  }

  ul {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
  }

  .name {
    font-family: var(--font-mono);
    font-size: var(--font-size-xs);
  }

  .tier {
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }

  .error {
    color: var(--color-danger);
  }
</style>
