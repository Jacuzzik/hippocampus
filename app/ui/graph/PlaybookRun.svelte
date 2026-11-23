<script lang="ts">
  // Playbooks (N.22): a note in the Playbooks folder is a playbook. Run sends its steps to the agent
  // picked, as one inbox message; the run then shows in the Inbox.
  import Button from "../controls/Button.svelte";
  import { invoke } from "@tauri-apps/api/core";
  import { addedAgents } from "../owner/addedAgents.svelte.ts";

  let { path }: { path: string } = $props();
  let agent = $state("hippoherman");
  let busy = $state(false);
  let done = $state<string | null>(null);
  let error = $state<string | null>(null);
  const agents = $derived([
    { id: "hippoherman", name: "Hippoherman" },
    ...addedAgents.list.map((a) => ({ id: a.id, name: a.name })),
  ]);

  async function run(): Promise<void> {
    busy = true;
    error = null;
    done = null;
    try {
      const answer = await invoke<{ steps: number }>("sidecar_call", {
        method: "playbook_run",
        params: { path, agent },
      });
      const name = agents.find((a) => a.id === agent)?.name ?? agent;
      done = `Sent ${answer.steps} steps to ${name}.`;
    } catch (cause) {
      error = String(cause);
    } finally {
      busy = false;
    }
  }
</script>

<section class="playbook" aria-label="Run this playbook">
  <label
    >Run with <select aria-label="Run playbook with" bind:value={agent}>
      {#each agents as one (one.id)}
        <option value={one.id}>{one.name}</option>
      {/each}
    </select></label
  >
  <Button disabled={busy} onclick={run}>Run playbook</Button>
  {#if done}<p class="muted" role="status">{done}</p>{/if}
  {#if error}<p class="muted" role="alert">{error}</p>{/if}
</section>

<style>
  .playbook {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: center;
    padding: var(--space-2) var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
  }
  .playbook p {
    flex: 1 1 100%;
    margin: 0;
  }
</style>
