<!-- The installed skills: name and what it does, a box to install one from a folder, and Remove with a second click to confirm. -->
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
  // Remove and install each take two clicks: the first asks, the second does it.
  let armed = $state<string | null>(null);
  let actionError = $state<string | null>(null);
  async function remove(name: string): Promise<void> {
    if (armed !== name) {
      armed = name;
      return;
    }
    armed = null;
    await change("remove_skill", { name, approve: true });
  }
  let installPath = $state("");
  let installArmed = $state(false);
  async function install(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    if (!installArmed) {
      installArmed = true;
      return;
    }
    installArmed = false;
    if (
      await change("install_skill", { path: installPath.trim(), approve: true })
    )
      installPath = "";
  }
  async function change(
    method: string,
    params: Record<string, unknown>,
  ): Promise<boolean> {
    actionError = null;
    try {
      skills = (
        await invoke<{ skills: Skill[] }>("sidecar_call", { method, params })
      ).skills;
      return true;
    } catch (cause) {
      actionError = String(cause);
      return false;
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
            <button
              type="button"
              class="act"
              aria-label={armed === skill.name
                ? `Confirm: remove ${skill.name}`
                : `Remove ${skill.name}`}
              onclick={() => void remove(skill.name)}
              onblur={() => (armed = null)}
              >{armed === skill.name ? "Confirm remove" : "Remove"}</button
            >
          </li>
        {/each}
      </ul>
    {/if}
  {/if}
  {#if loaded && !failed}
    <form class="install" aria-label="Install a skill" onsubmit={install}>
      <input
        type="text"
        aria-label="Skill folder to install"
        placeholder="Path to a skill folder"
        bind:value={installPath}
        oninput={() => (installArmed = false)}
      />
      <button type="submit" class="act" disabled={!installPath.trim()}
        >{installArmed ? "Confirm install" : "Install"}</button
      >
    </form>
    {#if actionError}<p class="error" role="alert">{actionError}</p>{/if}
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

  .install {
    display: flex;
    gap: var(--space-1);
    margin-top: var(--space-2);
  }

  .install input {
    flex: 1;
    min-width: 0;
  }

  .install input,
  .act {
    min-height: var(--layout-control-h);
    padding: 0 var(--space-2);
    color: var(--color-md-text);
    font: inherit;
    background: var(--color-md-surface);
    border: 1px solid var(--color-md-border);
    border-radius: var(--radius-sm);
  }

  .act {
    align-self: flex-start;
    cursor: pointer;
  }

  .act:disabled {
    opacity: 0.5;
    cursor: default;
  }

  .error {
    margin: var(--space-1) 0 0;
    color: var(--color-danger);
  }
</style>
