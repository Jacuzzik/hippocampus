<script lang="ts">
  // One chart or breakdown above a dashboard's tiles. Colours and spacing come from the design tokens.
  import TrendChart from "./TrendChart.svelte";
  import type { Panel } from "./model.ts";

  let { panel }: { panel: Panel } = $props();

  const RING = 40;
  const heatMax = $derived(
    panel.kind === "heat" ? Math.max(1, ...panel.values) : 1,
  );
</script>

<div class="panel">
  <div class="head">
    <span class="label">{panel.title}</span>
    <span class="note">{panel.note}</span>
  </div>

  {#if panel.kind === "trend"}
    <div class="body">
      <TrendChart values={panel.values} labels={panel.labels} label={panel.title} />
    </div>
  {:else if panel.kind === "breakdown"}
    <ul class="rows">
      {#each panel.rows as row (row.label)}
        <li class:warn={row.warn}>
          <span class="name">{row.label}</span>
          <span class="track" role="img" aria-label={`${Math.round(row.share * 100)}% of the whole`}>
            <span style:width={`${row.share * 100}%`}></span>
          </span>
          <span class="value">{row.value}</span>
        </li>
      {/each}
    </ul>
  {:else if panel.kind === "rings"}
    <ul class="rings">
      {#each panel.rings as ring (ring.label)}
        <li class:warn={ring.warn}>
          <svg viewBox="0 0 100 100" role="img" aria-label={`${ring.label} ${Math.round(ring.percent)} percent`}>
            <circle cx="50" cy="50" r={RING + 6} class="ring-track" />
            <circle
              cx="50"
              cy="50"
              r={RING + 6}
              class="ring-arc"
              stroke-dasharray={`${(Math.min(100, ring.percent) / 100) * 2 * Math.PI * (RING + 6)} ${2 * Math.PI * (RING + 6)}`}
              transform="rotate(-90 50 50)"
            />
            <text x="50" y="54" text-anchor="middle" class="ring-value">{Math.round(ring.percent)}%</text>
          </svg>
          <span class="name">{ring.label}</span>
        </li>
      {/each}
    </ul>
  {:else}
    <div class="heat" role="img" aria-label="Events per day over 13 weeks">
      {#each panel.values as value, i (i)}
        <span
          class="cell"
          style:--v={`${Math.max(12, Math.round((value / heatMax) * 100))}%`}
          title={`${value} event${value === 1 ? "" : "s"}`}
        ></span>
      {/each}
    </div>
    <div class="legend">
      <span>Fewer</span>
      <span class="swatches">
        <i style:--v="12%"></i><i style:--v="40%"></i><i style:--v="70%"></i><i style:--v="100%"></i>
      </span>
      <span>More</span>
    </div>
  {/if}
</div>

<style>
  .panel {
    display: grid;
    gap: var(--space-3);
    align-content: start;
    min-width: 0;
  }
  .head {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: var(--space-3);
    flex-wrap: wrap;
  }
  .note {
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
  }
  .body {
    position: relative;
    height: 200px;
  }
  .body :global(svg) {
    position: absolute;
    inset: 0;
    width: 100%;
    height: 100%;
  }

  .rows {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    gap: var(--space-2);
  }
  .rows li {
    display: grid;
    grid-template-columns: minmax(0, 160px) minmax(0, 1fr) auto;
    gap: var(--space-3);
    align-items: center;
    font-size: var(--font-size-sm);
  }
  .name {
    overflow-wrap: anywhere;
  }
  .track {
    display: block;
    height: 8px;
    border-radius: 999px;
    background: color-mix(in srgb, var(--color-text-muted) 18%, transparent);
    overflow: hidden;
  }
  .track > span {
    display: block;
    height: 100%;
    border-radius: inherit;
    background: var(--color-graph-1);
  }
  .rows li.warn .track > span {
    background: var(--color-danger);
  }
  .value {
    font-variant-numeric: tabular-nums;
    color: var(--color-text-muted);
  }

  .rings {
    list-style: none;
    margin: 0;
    padding: 0;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(96px, 1fr));
    gap: var(--space-3);
  }
  .rings li {
    display: grid;
    justify-items: center;
    gap: var(--space-2);
    font-size: var(--font-size-sm);
  }
  .rings svg {
    width: 96px;
    height: 96px;
  }
  .ring-track {
    fill: none;
    stroke: color-mix(in srgb, var(--color-text-muted) 18%, transparent);
    stroke-width: 8;
  }
  .ring-arc {
    fill: none;
    stroke: var(--color-graph-1);
    stroke-width: 8;
    stroke-linecap: round;
  }
  .rings li.warn .ring-arc {
    stroke: var(--color-danger);
  }
  .ring-value {
    fill: var(--color-text);
    font-size: 16px;
    font-variant-numeric: tabular-nums;
  }

  .heat {
    display: grid;
    grid-template-columns: repeat(13, minmax(0, 1fr));
    grid-template-rows: repeat(7, 14px);
    grid-auto-flow: column;
    gap: 3px;
  }
  .cell {
    border-radius: 2px;
    background: color-mix(
      in srgb,
      var(--color-graph-1) var(--v),
      var(--color-bg-1)
    );
  }
  .legend {
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--font-size-sm);
    color: var(--color-text-muted);
  }
  .swatches {
    display: inline-flex;
    gap: 3px;
  }
  .swatches i {
    width: 12px;
    height: 12px;
    border-radius: 2px;
    background: color-mix(in srgb, var(--color-graph-1) var(--v), var(--color-bg-1));
  }
</style>
