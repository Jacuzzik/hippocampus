<script lang="ts">
  // A line chart of one series over time, drawn to scale. Colours and text come from the design tokens.
  let {
    values,
    labels,
    label,
  }: { values: number[]; labels: string[]; label: string } = $props();

  const W = 900;
  const H = 200;
  const PL = 40;
  const PR = 8;
  const PT = 8;
  const PB = 24;

  // The top of the scale: the largest value, rounded up to a step of 1, 2, 5 or 10 times a power of ten.
  const top = $derived.by(() => {
    const max = Math.max(1, ...values);
    const power = 10 ** Math.floor(Math.log10(max));
    const step = [1, 2, 5, 10].find((s) => s * power * 4 >= max) ?? 10;
    return step * power * 4;
  });

  const x = (i: number) =>
    values.length > 1 ? PL + (i * (W - PL - PR)) / (values.length - 1) : PL;
  const y = (v: number) => PT + (1 - v / top) * (H - PT - PB);

  const path = $derived(
    values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" "),
  );
  const ticks = [0, 1, 2, 3, 4].map((t) => (t * top) / 4);
  const xIndexes = $derived(
    labels.length > 1 ? [0, Math.round((labels.length - 1) / 2), labels.length - 1] : [0],
  );
</script>

<svg viewBox="0 0 {W} {H}" role="img" aria-label={label} class="trend">
  {#each ticks as tick (tick)}
    <line x1={PL} x2={W - PR} y1={y(tick)} y2={y(tick)} class="grid" />
    <text x={PL - 6} y={y(tick) + 4} text-anchor="end" class="axis">{Math.round(tick)}</text>
  {/each}
  {#each xIndexes as i (i)}
    <text
      x={x(i)}
      y={H - 6}
      text-anchor={i === 0 ? "start" : i === labels.length - 1 ? "end" : "middle"}
      class="axis">{labels[i]}</text
    >
  {/each}
  <path d={path} class="line" />
  {#if values.length}
    <circle cx={x(values.length - 1)} cy={y(values.at(-1) ?? 0)} r="4" class="dot" />
  {/if}
</svg>

<style>
  .trend {
    display: block;
    width: 100%;
    height: auto;
    overflow: visible;
  }
  .grid {
    stroke: var(--color-border);
    stroke-width: 1;
  }
  .axis {
    fill: var(--color-text-muted);
    font-size: 12px;
    font-family: var(--font-ui);
  }
  .line {
    fill: none;
    stroke: var(--color-graph-1);
    stroke-width: 2;
    stroke-linejoin: round;
  }
  .dot {
    fill: var(--color-graph-1);
  }
</style>
