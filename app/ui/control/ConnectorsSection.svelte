<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import StatusCard, { type CardStatus } from "../controls/StatusCard.svelte";
  import Loading from "../controls/Loading.svelte";
  import { report } from "../notices.svelte.ts";

  // Everything the app can connect to, one card each, drawn from the backend's list (the `connectors` call).
  // A card says "Connected" only after a real check succeeded; one that cannot run yet says why.
  type Row = {
    id: string;
    kind: "check" | "card";
    name: string;
    what: string;
    state: CardStatus;
    reason: string;
    needs: string;
    details: string[];
    checked: string;
  };

  let rows = $state<Row[] | null>(null);
  let failed = $state(false);
  let testing = $state(false);

  async function load(fresh: boolean): Promise<void> {
    testing = true;
    try {
      rows = (
        await invoke<{ connectors: Row[] }>("sidecar_call", {
          method: "connectors",
          params: { fresh },
        })
      ).connectors;
      failed = false;
    } catch (cause) {
      if (rows === null) failed = true;
      else report("Could not check the connectors", cause);
    } finally {
      testing = false;
    }
  }
  onMount(() => void load(false));

  const checked = (iso: string): string =>
    new Date(iso).toLocaleTimeString([], {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  const live = $derived(rows?.filter((r) => r.kind === "check") ?? []);
  const cards = $derived(rows?.filter((r) => r.kind === "card") ?? []);
</script>

<section class="control-section" aria-labelledby="control-connectors">
  <h3 id="control-connectors">Connectors</h3>
  <p class="hint">
    What the app can reach, checked now, and what is not built yet. Model keys
    are on the Models and keys page.
  </p>
  {#if failed}
    <p class="muted">Could not read the connectors.</p>
  {:else if rows === null}
    <Loading what="the connectors" rows={4} />
  {:else}
    <div class="head">
      <h4>Checked now</h4>
      <button type="button" disabled={testing} onclick={() => void load(true)}
        >{testing ? "Checking…" : "Test again"}</button
      >
    </div>
    <div class="grid">
      {#each live as row (row.id)}
        <StatusCard name={row.name} what={row.what} status={row.state}>
          <p class="why">{row.reason}</p>
          {#if row.needs && row.state !== "Connected"}
            <p class="why">Needs: {row.needs}.</p>
          {/if}
          {#if row.details.length}
            <ul aria-label={`${row.name} details`}>
              {#each row.details as line (line)}<li>{line}</li>{/each}
            </ul>
          {/if}
          <p class="when">Checked {checked(row.checked)}</p>
        </StatusCard>
      {/each}
    </div>
    <h4>Not built yet</h4>
    <div class="grid">
      {#each cards as row (row.id)}
        <StatusCard
          name={row.name}
          what={row.what}
          status={row.state}
          reason={`${row.reason} Needs: ${row.needs}.`}
        />
      {/each}
    </div>
  {/if}
</section>

<style>
  h4 {
    margin: var(--space-3) 0 var(--space-2);
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: var(--space-2);
  }

  .head {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: var(--space-2);
  }

  .why,
  .when {
    flex-basis: 100%;
    margin: 0;
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }

  .when {
    color: var(--color-text-subtle);
  }

  ul {
    flex-basis: 100%;
    margin: 0;
    padding-left: var(--space-4);
    max-height: 8em;
    overflow: auto;
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
    overflow-wrap: anywhere;
  }
</style>
