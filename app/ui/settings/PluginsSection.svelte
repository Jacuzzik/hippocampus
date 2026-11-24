<script lang="ts">
  import { onMount } from "svelte";
  import Button from "../controls/Button.svelte";
  import Toggle from "../controls/Toggle.svelte";
  import { call, fileBase64 } from "./call";

  // D.07: a plugin is a Claude Code plugin (.zip with .claude-plugin/plugin.json). Each switched-on one reaches every Claude agent.
  type Row = {
    name: string;
    version: string;
    description: string;
    skills: number;
    commands: number;
    helpers: number;
    servers: string[];
    enabled: boolean;
  };
  let rows = $state<Row[]>([]);
  let error = $state("");
  let busy = $state(false);
  let picker: HTMLInputElement | undefined = $state();

  async function run(method: string, params = {}): Promise<void> {
    busy = true;
    error = "";
    try {
      rows = (await call<{ plugins: Row[] }>(method, params)).plugins;
    } catch (cause) {
      error = String(cause);
    } finally {
      busy = false;
    }
  }
  async function add(event: Event): Promise<void> {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    input.value = "";
    if (file)
      await run("plugin_install", {
        name: file.name,
        data: await fileBase64(file),
      });
  }
  onMount(() => void run("plugin_list"));
</script>

<section class="control-section" aria-labelledby="plugins-title">
  <h3 id="plugins-title">Plugins</h3>
  <p class="hint">
    A plugin adds several skills, commands, helpers and tool servers in one
    install. Add a Claude Code plugin as a .zip. Each switched-on plugin reaches
    every agent on Claude Code the next time it starts.
  </p>
  <input
    bind:this={picker}
    type="file"
    accept=".zip"
    hidden
    aria-label="Plugin file"
    onchange={(e) => void add(e)}
  />
  <Button disabled={busy} onclick={() => picker?.click()}>Add a plugin</Button>
  {#if rows.length === 0}
    <p class="muted">No plugins installed.</p>
  {:else}
    <ul aria-label="Plugins">
      {#each rows as row (row.name)}
        <li>
          <strong>{row.name}</strong>
          {#if row.version}<span class="muted">{row.version}</span>{/if}
          <span>{row.description}</span>
          <span class="muted"
            >{row.skills} skills, {row.commands} commands, {row.helpers} helpers{row
              .servers.length
              ? `, servers: ${row.servers.join(", ")}`
              : ""}</span
          >
          <Toggle
            ariaLabel={`Use ${row.name}`}
            checked={row.enabled}
            label={row.enabled ? "On" : "Off"}
            onchange={(on) => void run("plugin_enable", { name: row.name, on })}
          />
          <Button
            size="sm"
            variant="ghost"
            onclick={() => void run("plugin_remove", { name: row.name })}
            >Remove</Button
          >
        </li>
      {/each}
    </ul>
  {/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>

<style>
  li {
    display: flex;
    gap: var(--space-2);
    align-items: center;
    flex-wrap: wrap;
    margin-top: var(--space-2);
  }
</style>
