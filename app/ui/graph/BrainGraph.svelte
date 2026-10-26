<script lang="ts">
  import { untrack } from "svelte";
  import { token } from "./colors";
  import type { Rgba } from "./renderer";
  import { BrainRenderer } from "./renderer";
  import {
    centerOn,
    hitTest,
    LOW_POWER,
    layout,
    matchFilter,
    zoomAt,
    type Camera,
    type GraphData,
  } from "./model";

  // The note list in the sidebar owns the search, tag filter and selection; the graph draws them.
  let {
    data,
    query = "",
    tag = null,
    selectedId = null,
    onselect,
  }: {
    data: GraphData;
    query?: string;
    tag?: string | null;
    selectedId?: string | null;
    onselect: (id: string | null) => void;
  } = $props();

  let canvas: HTMLCanvasElement | undefined = $state();
  let error = $state<string | null>(null);
  let cam = $state<Camera>({ x: 0, y: 0, zoom: 1 });

  // Plain variables: they are rebuilt from `data` and read by the draw loop, not by the template.
  let renderer: BrainRenderer | null = null;
  let pos = new Float32Array(0);
  let colours: { node: Rgba; hot: Rgba; edge: Rgba; bg: Rgba } | null = null;
  let frame = 0;

  const index = $derived(new Map(data.nodes.map((n, i) => [n.id, i])));
  const selected = $derived(selectedId ? (index.get(selectedId) ?? -1) : -1);
  const matched = $derived(matchFilter(data.nodes, { query, tag }));
  const node = $derived(selected >= 0 ? data.nodes[selected] : undefined);
  const outgoing = $derived(
    node
      ? data.edges
          .filter(([a, b]) => a === node.id && b !== node.id)
          .map(([, b]) => b)
      : [],
  );
  const incoming = $derived(
    node
      ? data.edges
          .filter(([a, b]) => b === node.id && a !== node.id)
          .map(([a]) => a)
      : [],
  );

  function schedule(): void {
    if (!frame) frame = requestAnimationFrame(draw);
  }

  function draw(): void {
    frame = 0;
    if (renderer && colours) renderer.draw(cam, colours.bg, colours.edge);
  }

  function size(): [number, number] {
    return [canvas?.clientWidth ?? 0, canvas?.clientHeight ?? 0];
  }

  function fitAll(): void {
    if (!pos.length) return;
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (let i = 0; i < pos.length; i += 2) {
      minX = Math.min(minX, pos[i] ?? 0);
      maxX = Math.max(maxX, pos[i] ?? 0);
      minY = Math.min(minY, pos[i + 1] ?? 0);
      maxY = Math.max(maxY, pos[i + 1] ?? 0);
    }
    const [w, h] = size();
    const zoom = Math.min(w / (maxX - minX + 40), h / (maxY - minY + 40));
    cam = centerOn((minX + maxX) / 2, (minY + maxY) / 2, zoom, w, h);
    schedule();
  }

  function title(id: string): string {
    return data.nodes[index.get(id) ?? -1]?.title ?? id;
  }

  function open(id: string): void {
    onselect(id);
  }

  // Bring a selected node into view, unless it is already on screen (a click on the canvas).
  $effect(() => {
    const i = selected;
    if (i < 0) return;
    untrack(() => {
      const sx = (pos[2 * i] ?? 0) * cam.zoom + cam.x;
      const sy = (pos[2 * i + 1] ?? 0) * cam.zoom + cam.y;
      const [w, h] = size();
      if (sx >= 0 && sy >= 0 && sx <= w && sy <= h) return;
      cam = centerOn(
        pos[2 * i] ?? 0,
        pos[2 * i + 1] ?? 0,
        Math.max(cam.zoom, 1),
        w,
        h,
      );
      schedule();
    });
  });

  function pushStyle(): void {
    if (!renderer || !colours) return;
    const n = data.nodes.length;
    const colors = new Float32Array(n * 4);
    const radii = new Float32Array(n);
    for (let i = 0; i < n; i++) {
      const isSel = i === selected;
      const base = isSel ? colours.hot : colours.node;
      const alpha = matched[i] ? base[3] : base[3] * 0.15;
      colors.set([base[0], base[1], base[2], alpha], i * 4);
      radii[i] = isSel ? 7 : 4;
    }
    renderer.setColors(colors);
    renderer.setRadii(radii);
    schedule();
  }

  // Create the WebGL context once per canvas and keep the canvas size in step with its box.
  $effect(() => {
    const c = canvas;
    if (!c) return;
    let r: BrainRenderer;
    try {
      r = new BrainRenderer(c);
    } catch (e) {
      error = e instanceof Error ? e.message : String(e);
      return;
    }
    renderer = r;
    colours = {
      node: token("accent"),
      hot: token("confirm"),
      edge: [...token("link").slice(0, 3), 0.3] as Rgba,
      bg: token("bg-0"),
    };
    const fit = () => {
      r.resize(c.clientWidth, c.clientHeight, LOW_POWER.dprCap);
      schedule();
    };
    const observer = new ResizeObserver(fit);
    observer.observe(c);
    fit();

    let drag: { x: number; y: number; cam: Camera; moved: boolean } | null =
      null;
    const local = (e: PointerEvent | WheelEvent) => {
      const rect = c.getBoundingClientRect();
      return [e.clientX - rect.left, e.clientY - rect.top] as const;
    };
    const onDown = (e: PointerEvent) => {
      c.setPointerCapture(e.pointerId);
      const [x, y] = local(e);
      drag = { x, y, cam, moved: false };
    };
    const onMove = (e: PointerEvent) => {
      if (!drag) return;
      const [x, y] = local(e);
      const dx = x - drag.x;
      const dy = y - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 4) drag.moved = true;
      cam = { ...drag.cam, x: drag.cam.x + dx, y: drag.cam.y + dy };
      schedule();
    };
    const onUp = (e: PointerEvent) => {
      if (!drag) return;
      const [x, y] = local(e);
      if (!drag.moved) {
        const hit = hitTest(pos, cam, x, y, 8);
        onselect(hit >= 0 ? (data.nodes[hit]?.id ?? null) : null);
      }
      drag = null;
    };
    const onWheel = (e: WheelEvent) => {
      e.preventDefault();
      const [x, y] = local(e);
      cam = zoomAt(cam, x, y, Math.exp(-e.deltaY * 0.0015));
      schedule();
    };
    c.addEventListener("pointerdown", onDown);
    c.addEventListener("pointermove", onMove);
    c.addEventListener("pointerup", onUp);
    c.addEventListener("pointercancel", () => (drag = null));
    c.addEventListener("wheel", onWheel, { passive: false });

    return () => {
      observer.disconnect();
      c.removeEventListener("pointerdown", onDown);
      c.removeEventListener("pointermove", onMove);
      c.removeEventListener("pointerup", onUp);
      if (frame) cancelAnimationFrame(frame);
      frame = 0;
      r.dispose();
      renderer = null;
      colours = null;
    };
  });

  // Lay out the graph again whenever the notes change.
  $effect(() => {
    void data;
    untrack(relayout);
  });

  function relayout(): void {
    const r = renderer;
    if (!r) return;
    const pairs: [number, number][] = [];
    for (const [a, b] of data.edges) {
      const ia = index.get(a);
      const ib = index.get(b);
      if (ia !== undefined && ib !== undefined && ia !== ib)
        pairs.push([ia, ib]);
    }
    pos = layout(data.nodes.length, pairs);
    const flat = new Uint32Array(pairs.length * 2);
    pairs.forEach(([a, b], i) => {
      flat[2 * i] = a;
      flat[2 * i + 1] = b;
    });
    r.setGraph(pos, flat);
    fitAll();
    pushStyle();
  }

  // Re-colour when the filter or the selection changes.
  $effect(() => {
    void matched;
    void selected;
    pushStyle();
  });

  function onWindowKey(e: KeyboardEvent): void {
    if (e.key === "Escape" && selected >= 0) onselect(null);
  }
</script>

<svelte:window onkeydown={onWindowKey} />

<div class="brain">
  <div
    class="canvas-box"
    role="img"
    aria-label="Brain graph of {data.nodes.length} notes"
  >
    <canvas bind:this={canvas} class="canvas"></canvas>
  </div>

  {#if error}
    <p class="notice" role="alert">The graph cannot be drawn: {error}</p>
  {:else if data.nodes.length === 0}
    <p class="notice">This vault has no notes yet.</p>
  {/if}

  {#if node}
    <aside class="drawer" aria-label="Note details">
      <header>
        <h2>{node.title}</h2>
        <button
          type="button"
          class="close"
          aria-label="Close note details"
          onclick={() => onselect(null)}>×</button
        >
      </header>
      <p class="path">{node.id}</p>
      {#if node.tags.length}
        <p class="tags">{node.tags.map((t) => `#${t}`).join(" ")}</p>
      {/if}
      <h3>Links to</h3>
      {#if outgoing.length}
        <ul>
          {#each outgoing as id (id)}
            <li>
              <button type="button" onclick={() => open(id)}>{title(id)}</button
              >
            </li>
          {/each}
        </ul>
      {:else}
        <p class="muted">None</p>
      {/if}
      <h3>Linked from</h3>
      {#if incoming.length}
        <ul>
          {#each incoming as id (id)}
            <li>
              <button type="button" onclick={() => open(id)}>{title(id)}</button
              >
            </li>
          {/each}
        </ul>
      {:else}
        <p class="muted">None</p>
      {/if}
    </aside>
  {/if}
</div>

<style>
  .brain {
    position: relative;
    width: 100%;
    height: 100%;
    overflow: hidden;
  }

  .canvas-box,
  .canvas {
    width: 100%;
    height: 100%;
  }

  .canvas {
    display: block;
    cursor: grab;
    touch-action: none;
  }

  .canvas:active {
    cursor: grabbing;
  }

  .notice {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    margin: 0;
    color: var(--color-text-muted);
  }

  .drawer {
    position: absolute;
    top: var(--space-3);
    right: var(--space-3);
    bottom: var(--space-3);
    width: min(320px, calc(100% - 2 * var(--space-3)));
    overflow-y: auto;
    padding: var(--space-4);
    border-radius: var(--radius-md);
    background: var(--color-bg-1);
    border: 1px solid var(--color-border);
  }

  .drawer header {
    display: flex;
    justify-content: space-between;
    align-items: start;
    gap: var(--space-2);
  }

  h2,
  h3 {
    margin: 0;
    color: var(--color-text);
  }

  h2 {
    font-size: var(--font-size-md);
  }

  h3 {
    margin-top: var(--space-4);
    font-size: var(--font-size-sm);
  }

  .path,
  .tags,
  .muted {
    margin: var(--space-1) 0 0;
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }

  ul {
    margin: var(--space-2) 0 0;
    padding: 0;
    list-style: none;
  }

  li + li {
    margin-top: var(--space-1);
  }

  button {
    font: inherit;
    color: var(--color-link);
    background: none;
    border: 0;
    padding: 0;
    text-align: left;
    cursor: pointer;
  }

  .close {
    color: var(--color-text-muted);
    font-size: var(--font-size-lg);
    line-height: 1;
  }
</style>
