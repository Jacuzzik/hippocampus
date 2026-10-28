<script lang="ts">
  import { ORB_LABELS } from "../assistant/model";
  import { assistant } from "../assistant/session.svelte";

  // The agents on this floor. Only the assistant exists in the app today.
  const agents = $derived([
    {
      id: "assistant",
      name: "Assistant",
      state: ORB_LABELS[assistant.chat.orb],
    },
  ]);
</script>

<section class="agents" aria-label="Agent status">
  <h3>Agents</h3>
  <ul>
    {#each agents as agent (agent.id)}
      <li>
        <span class="name">{agent.name}</span>
        <span
          class="state"
          role="status"
          aria-label="{agent.name}: {agent.state}">{agent.state}</span
        >
      </li>
    {/each}
  </ul>
</section>

<style>
  .agents {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    padding: var(--space-2) var(--space-3);
    border-bottom: 1px solid var(--color-border);
  }

  h3 {
    margin: 0;
    font-size: var(--font-size-xs);
    font-weight: 600;
    color: var(--color-text-subtle);
  }

  ul {
    margin: 0;
    padding: 0;
    list-style: none;
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    font-size: var(--font-size-xs);
  }

  li {
    display: flex;
    justify-content: space-between;
    gap: var(--space-2);
  }

  .state {
    color: var(--color-text-muted);
  }
</style>
