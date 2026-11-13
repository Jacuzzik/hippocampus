<!-- The installed skills, read only: name, what it does and where it lives. -->
<script lang="ts">
  import Loading from "../controls/Loading.svelte";
  import { onMount } from "svelte";
  import { every } from "../poll.ts";
  import { flagOn } from "../flags.svelte.ts";
  import { invoke } from "@tauri-apps/api/core";

  type Skill = { name: string; description: string; path: string };

  let skills = $state<Skill[]>([]);
  let failed = $state(false);
  let query = $state("");
  const shown = $derived(
    skills.filter((skill) =>
      `${skill.name} ${skill.description}`
        .toLowerCase()
        .includes(query.trim().toLowerCase()),
    ),
  );
  // False until the first answer (or failure), so an empty list is not shown while it is still loading.
  let loaded = $state(false);

  // Read again every few seconds while this tab is open, so it does not go stale.
  async function load(): Promise<void> {
    try {
      skills = (
        await invoke<{ skills: Skill[] }>("sidecar_call", { method: "skills" })
      ).skills;
      failed = false;
      loaded = true;
    } catch (cause) {
      failed = true;
      loaded = true;
      console.error("Could not read the skills", cause);
    }
  }
  onMount(() => {
    void load();
    return flagOn("panelRefresh") ? every(load, 5000) : undefined;
  });
</script>

<section class="skills" aria-label="Skills">
  {#if !loaded}
    <Loading what="the skills" />
  {:else if failed}
    <p class="muted">Could not read the skills.</p>
  {:else if skills.length === 0}
    <p class="muted">No skills installed yet.</p>
  {:else}
    <input
      type="search"
      class="find"
      aria-label="Search skills"
      placeholder="Search skills"
      bind:value={query}
    />
    {#if shown.length === 0}
      <p class="muted">No skill matches "{query.trim()}".</p>
    {:else}
      <ul>
        {#each shown as skill (skill.name)}
          <li>
            <span class="name">{skill.name}</span>
            <span class="desc">{skill.description}</span>
          </li>
        {/each}
      </ul>
    {/if}
  {/if}
</section>

<style>
  .skills {
    font-family: var(--font-ui);
    font-size: var(--font-size-xs);
    color: var(--color-md-text);
    overflow-y: auto;
  }

  .find {
    width: 100%;
    margin-bottom: var(--space-1);
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
