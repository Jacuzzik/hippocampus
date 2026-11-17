<!-- 7.29 First-run setup: the Doctor's checks as a checklist, each with a mark and the next step for a gap.
     Shown in Setup and account, and opened by itself once, on the first start. -->
<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import Loading from "../controls/Loading.svelte";

  type Check = {
    name: string;
    state: "ok" | "warn" | "bad";
    found: string;
    fix: string;
  };
  const MARK = { ok: "✓", warn: "!", bad: "✗" } as const;
  const SAID = { ok: "Ready", warn: "Needs a look", bad: "Missing" } as const;

  let checks = $state<Check[] | null>(null);
  let error = $state<string | null>(null);
  let busy = $state(false);

  async function run(): Promise<void> {
    busy = true;
    error = null;
    try {
      checks = (
        await invoke<{ checks: Check[] }>("sidecar_call", { method: "doctor" })
      ).checks;
    } catch (cause) {
      error = String(cause);
    } finally {
      busy = false;
    }
  }
  onMount(() => void run());

  const ready = $derived(checks?.filter((c) => c.state === "ok").length ?? 0);
</script>

<div class="setup">
  {#if checks === null && !error}
    <Loading what="the setup checks" />
  {:else if checks}
    <p class="muted">{ready} of {checks.length} ready.</p>
    <ul aria-label="Setup checks">
      {#each checks as check (check.name)}
        <li class={check.state}>
          <span class="mark" aria-hidden="true">{MARK[check.state]}</span>
          <span class="what">
            <strong>{check.name}</strong>
            <span class="sr">{SAID[check.state]}.</span>
            {check.found}
            {#if check.state !== "ok" && check.fix}
              <span class="fix">{check.fix}</span>
            {/if}
          </span>
        </li>
      {/each}
    </ul>
  {/if}
  {#if error}<p role="alert" class="error">{error}</p>{/if}
  <div>
    <button type="button" disabled={busy} onclick={run}
      >{busy ? "Checking…" : "Check again"}</button
    >
  </div>
</div>

<style>
  .setup {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
  }

  ul {
    display: flex;
    flex-direction: column;
    gap: var(--space-1);
    margin: 0;
    padding: 0;
    list-style: none;
  }

  li {
    display: flex;
    gap: var(--space-2);
    align-items: baseline;
  }

  .mark {
    flex: none;
    width: var(--size-16);
    text-align: center;
    font-weight: 700;
  }

  .ok .mark {
    color: var(--color-accent);
  }

  .warn .mark,
  .bad .mark {
    color: var(--color-danger);
  }

  .what {
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .fix {
    color: var(--color-text-muted);
  }

  button {
    min-height: var(--size-28);
    font: inherit;
    color: var(--color-text);
    background: var(--color-bg-0);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    padding: var(--space-1) var(--space-3);
    cursor: pointer;
  }

  .muted {
    margin: 0;
    color: var(--color-text-muted);
  }

  .error {
    color: var(--color-danger);
  }

  .sr {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
  }
</style>
