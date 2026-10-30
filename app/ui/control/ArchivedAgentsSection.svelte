<script lang="ts">
  import {
    addedAgents,
    archived,
    setArchived,
  } from "../owner/addedAgents.svelte";

  // Agents archived from their card menu in the bottom bar; restoring one shows it there again.
  const hidden = $derived(
    addedAgents.list.filter((a) => archived.ids.includes(a.id)),
  );
</script>

<section class="control-section" aria-labelledby="control-archived">
  <h3 id="control-archived">Archived agents</h3>
  {#if hidden.length === 0}
    <p class="muted">
      No archived agents. Archive a card from its menu in the bottom bar.
    </p>
  {:else}
    <ul>
      {#each hidden as agent (agent.id)}
        <li>
          {agent.name}
          <button type="button" onclick={() => setArchived(agent.id, false)}
            >Restore</button
          >
        </li>
      {/each}
    </ul>
  {/if}
</section>
