<script lang="ts">
  import Button from "../controls/Button.svelte";
  import ErrorRow from "../controls/ErrorRow.svelte";
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";

  // What the app can use: MCP servers, skills and plugins. Skills can be installed from a folder
  // and removed (the install_skill and remove_skill calls).
  type Skill = { name: string; description: string };

  let skills = $state<Skill[]>([]);
  let armed = $state<string | null>(null);
  let error = $state<string | null>(null);
  // True while an install or remove runs, so the buttons cannot be pressed twice (13.03).
  let busy = $state<"install" | "remove" | null>(null);

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
    busy = "remove";
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
    } finally {
      busy = null;
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
    busy = "install";
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
    } finally {
      busy = null;
    }
  }

  onMount(() => void load());
</script>

<section class="control-section" aria-labelledby="control-capabilities">
  <h3 id="control-capabilities">Capabilities</h3>
  <p class="hint">
    Tools and skills the assistant can use. You can install a skill from a
    folder and remove one here.
  </p>
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
          <Button
            disabled={busy !== null}
            onclick={() => removeSkill(skill.name)}
          >
            {armed === skill.name ? "Confirm remove" : "Remove"}
          </Button>
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
    <Button
      disabled={!installPath.trim() || busy !== null}
      onclick={installSkill}
    >
      {busy === "install"
        ? "Installing…"
        : installArmed
          ? `Confirm install of ${installPath.trim()}`
          : "Install"}
    </Button>
  </div>
  {#if error}<ErrorRow message={error} onretry={load} />{/if}
</section>

<style>
  h4 {
    margin: var(--space-3) 0 var(--space-1);
    font-size: var(--font-size-sm);
  }

  ul {
    margin: 0;
    padding-inline-start: 0;
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
