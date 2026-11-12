<!-- The installed skills, read only: name, what it does and where it lives. -->
<script lang="ts">
  import { onMount } from "svelte";
  import { every } from "../poll.ts";
  import { flagOn } from "../flags.svelte.ts";
  import { invoke } from "@tauri-apps/api/core";

  type Skill = { name: string; description: string; path: string };

  let skills = $state<Skill[]>([]);
  let failed = $state(false);

  // Read again every few seconds while this tab is open, so it does not go stale.
  async function load(): Promise<void> {
    try {
      skills = (await invoke<{ skills: Skill[] }>("sidecar_call", { method: "skills" })).skills;
      failed = false;
    } catch (cause) {
      failed = true;
      console.error("Could not read the skills", cause);
    }
  }
  onMount(() => {
    void load();
    return flagOn("panelRefresh") ? every(load, 5000) : undefined;
  });
</script>

<section class="skills" aria-label="Skills">
  {#if failed}
    <p class="muted">Could not read the skills.</p>
  {:else if skills.length === 0}
    <p class="muted">No skills installed yet.</p>
  {:else}
    <ul>
      {#each skills as skill (skill.name)}
        <li>
          <span class="name">{skill.name}</span>
          <span class="desc">{skill.description}</span>
        </li>
      {/each}
    </ul>
  {/if}
</section>

<style>
  .skills {
    font-family: var(--font-ui);
    font-size: var(--font-size-xs);
    color: var(--color-md-text);
    overflow-y: auto;
  }

  ul {
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    padding: var(--space-2) 0;
    border-bottom: 1px solid var(--color-border);
  }

  .name {
    color: var(--color-md-accent);
  }

  .desc {
    color: var(--color-md-text-muted);
  }

  .muted {
    color: var(--color-md-text-muted);
  }
</style>
