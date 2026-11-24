<script lang="ts">
  import { onMount } from "svelte";
  import Button from "../controls/Button.svelte";
  import { call } from "./call";

  // 7.31: counts from this computer's own activity log. Read-only; nothing is sent anywhere.
  type Count = { name: string; count: number };
  type Stats = {
    statement: string;
    total: number;
    since: string | null;
    kinds: Count[];
    tools: Count[];
    agents: Count[];
    approvals: { asked: number; approved: number; declined: number };
    failed_tools: number;
    days: { day: string; count: number }[];
    file: string;
  };
  let stats = $state<Stats | null>(null);
  let error = $state("");
  let busy = $state(false);

  async function load(): Promise<void> {
    busy = true;
    error = "";
    try {
      stats = await call<Stats>("usage_stats");
    } catch (cause) {
      error = String(cause);
    } finally {
      busy = false;
    }
  }
  onMount(() => void load());
  const peak = $derived(
    Math.max(1, ...(stats?.days.map((d) => d.count) ?? [])),
  );
</script>

<section class="control-section" aria-labelledby="usage-title">
  <h3 id="usage-title">Usage statistics</h3>
  {#if stats}
    <p class="hint">{stats.statement}</p>
    <p>
      {stats.total} events{stats.since ? ` since ${stats.since}` : ""}. Source:
      <code>{stats.file}</code>
    </p>
    <h4>Last 14 days</h4>
    <ul class="days" aria-label="Events per day">
      {#each stats.days as d (d.day)}
        <li title="{d.day}: {d.count}">
          <span class="bar" style:height="{(d.count / peak) * 100}%"></span>
          <span class="sr">{d.day}: {d.count}</span>
        </li>
      {/each}
    </ul>
    <p>
      Approvals asked: {stats.approvals.asked} ({stats.approvals.approved} approved,
      {stats.approvals.declined} declined). Tool calls that failed or were refused:
      {stats.failed_tools}.
    </p>
    {#each [["By kind", stats.kinds], ["Most used tools", stats.tools], ["Busiest agents", stats.agents]] as [title, rows] (title)}
      {#if (rows as Count[]).length}
        <h4>{title}</h4>
        <ul class="plain" aria-label={title as string}>
          {#each rows as Count[] as row (row.name)}
            <li>{row.name}: {row.count}</li>
          {/each}
        </ul>
      {/if}
    {/each}
  {/if}
  <Button disabled={busy} onclick={() => void load()}>Refresh</Button>
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>

<style>
  .days {
    display: flex;
    align-items: flex-end;
    gap: var(--space-1);
    height: 64px;
    list-style: none;
    padding: 0;
  }
  .days li {
    flex: 1;
    height: 100%;
    display: flex;
    align-items: flex-end;
  }
  .bar {
    display: block;
    width: 100%;
    min-height: 2px;
    background: var(--color-accent);
    border-radius: var(--radius-sm);
  }
  .plain {
    list-style: none;
    padding: 0;
    margin: 0 0 var(--space-2);
  }
  .sr {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip-path: inset(50%);
  }
</style>
