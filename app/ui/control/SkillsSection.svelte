<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";

  // Installed skills: folders under skills/ that hold a SKILL.md file.
  type Skill = { name: string; description: string; path: string };

  let skills = $state<Skill[]>([]);
  let armed = $state<string | null>(null);
  let copied = $state<string | null>(null);
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
  async function remove(name: string): Promise<void> {
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
    } catch (cause) {
      error = String(cause);
    }
  }

  async function copy(skill: Skill): Promise<void> {
    try {
      await navigator.clipboard.writeText(skill.path);
      copied = skill.name;
    } catch {
      error = "Could not copy. The path is shown above.";
    }
  }

  onMount(() => void load());
</script>

<section class="control-section" aria-labelledby="control-skills">
  <h3 id="control-skills">Skills</h3>
  <p class="hint">Folders in the skills folder that hold a SKILL.md file.</p>
  {#if skills.length === 0}
    <p class="muted">No skills are installed.</p>
  {:else}
    <ul aria-label="Installed skills">
      {#each skills as skill (skill.name)}
        <li>
          <strong>{skill.name}</strong>
          {#if skill.description}<span class="muted">
              · {skill.description}</span
            >{/if}
          <p class="mono muted">{skill.path}</p>
          <div class="row">
            <button type="button" onclick={() => copy(skill)}>
              {copied === skill.name ? "Path copied" : "Copy folder path"}
            </button>
            <button type="button" onclick={() => remove(skill.name)}>
              {armed === skill.name ? "Confirm remove" : "Remove"}
            </button>
          </div>
        </li>
      {/each}
    </ul>
  {/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>
