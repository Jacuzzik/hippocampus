<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";

  // What the app can use: MCP servers, skills and plugins. Skills can be installed from a folder
  // and removed (the install_skill and remove_skill calls). MCP and plugins stay Not set up.
  type Skill = { name: string; description: string };
  // MCP servers and plugins are not read from disk yet, so these lists are empty for now.
  const mcpServers: { name: string }[] = [];
  const plugins: { name: string }[] = [];

  let skills = $state<Skill[]>([]);
  let armed = $state<string | null>(null);
  let error = $state<string | null>(null);

  async function load(): Promise<void> {
    try {
      skills = (
        await invoke<{ skills: Skill[] }>("sidecar_call", { method: "skills" })
      ).skills;
    } catch (cause) {
      error = String(cause);
    }
  }

  // Removing a skill takes two clicks: the first arms it, the second approves it.
  async function removeSkill(name: string): Promise<void> {
    if (armed !== name) {
      armed = name;
      return;
    }
    armed = null;
    try {
      skills = (
        await invoke<{ skills: Skill[] }>("sidecar_call", {
          method: "remove_skill",
          params: { name, approve: true },
        })
      ).skills;
      error = null;
    } catch (cause) {
      error = String(cause);
    }
  }

  // Installing copies a skill folder the user names into the skills folder. Two clicks, as for remove.
  let installPath = $state("");
  let installArmed = $state(false);

  async function installSkill(): Promise<void> {
    if (!installArmed) {
      installArmed = true;
      return;
    }
    installArmed = false;
    try {
      skills = (
        await invoke<{ skills: Skill[] }>("sidecar_call", {
          method: "install_skill",
          params: { path: installPath.trim(), approve: true },
        })
      ).skills;
      installPath = "";
      error = null;
    } catch (cause) {
      error = String(cause);
    }
  }

  onMount(() => void load());
</script>

<section class="control-section" aria-labelledby="control-capabilities">
  <h3 id="control-capabilities">Capabilities</h3>
  <p class="hint">
    Tools and skills the assistant can use. You can install a skill from a folder
    and remove one here. MCP servers and plugins are Not set up in this build.
  </p>
  {#each [{ title: "MCP servers", items: mcpServers }, { title: "Plugins", items: plugins }] as group (group.title)}
    <h4>{group.title}</h4>
    {#if group.items.length === 0}
      <p class="muted">None installed.</p>
    {:else}
      <ul>
        {#each group.items as item (item.name)}
          <li class="cap">
            <span>{item.name}</span>
            <button type="button" disabled>Remove: Not set up</button>
          </li>
        {/each}
      </ul>
    {/if}
    <div class="row">
      <button type="button" disabled>Install: Not set up</button>
    </div>
  {/each}
  <h4>Skill folders</h4>
  {#if skills.length === 0}
    <p class="muted">None installed.</p>
  {:else}
    <ul>
      {#each skills as skill (skill.name)}
        <li class="cap">
          <span
            >{skill.name} <span class="muted">{skill.description}</span></span
          >
          <button type="button" onclick={() => removeSkill(skill.name)}>
            {armed === skill.name ? "Confirm remove" : "Remove"}
          </button>
        </li>
      {/each}
    </ul>
  {/if}
  <div class="row">
    <input
      type="text"
      aria-label="Skill folder path"
      placeholder="Path to a skill folder"
      bind:value={installPath}
      oninput={() => (installArmed = false)}
    />
    <button type="button" disabled={!installPath.trim()} onclick={installSkill}>
      {installArmed ? `Confirm install of ${installPath.trim()}` : "Install"}
    </button>
  </div>
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>

<style>
  h4 {
    margin: var(--space-3) 0 var(--space-1);
    font-size: var(--font-size-sm);
  }

  ul {
    margin: 0;
    padding-left: 0;
    list-style: none;
  }

  .cap {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    justify-content: space-between;
    padding: var(--space-1) 0;
  }
</style>
