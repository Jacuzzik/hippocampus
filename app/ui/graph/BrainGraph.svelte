<script lang="ts">
  import { untrack } from "svelte";
  import { SvelteMap } from "svelte/reactivity";
  import { token } from "./colors";
  import type { Rgba } from "./renderer";
  import { BrainRenderer } from "./renderer";
  import {
    centerOn,
    hitTest,
    LOW_POWER,
    layout,
    matchFilter,
    mulberry32,
    zoomAt,
    type Camera,
    type GraphData,
  } from "./model";

  const LABEL_GAP = 4;
  const LABEL_H = 14;
  const MAX_LABELS = 300;

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
  let labelLayer: HTMLDivElement | undefined = $state();
  let labels = $state<{ text: string; x: number; y: number }[]>([]);
  let error = $state<string | null>(null);
  let cam = $state<Camera>({ x: 0, y: 0, zoom: 1 });

  // Plain variables: they are rebuilt from `data` and read by the draw loop, not by the template.
  let renderer: BrainRenderer | null = null;
  // `home` is the laid-out position; `pos` is home plus the drift, and is what is drawn and hit-tested.
  let home: Float32Array<ArrayBuffer> = new Float32Array(0);
  let pos: Float32Array<ArrayBuffer> = new Float32Array(0);
  // Per node: x and y drift amplitude, x and y angular speed, x and y phase. Six floats each.
  let drift: Float32Array<ArrayBuffer> = new Float32Array(0);
  let clock = 0;
  let last = 0;
  let dragging = false;
  // Reduced motion: the nodes stay still.
  const calm =
    typeof matchMedia === "function" &&
    matchMedia("(prefers-reduced-motion: reduce)").matches;
  const widths = new SvelteMap<string, number>();
  const measurer = document.createElement("canvas").getContext("2d");
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

  // The nodes float only while nothing is selected and no drag is under way.
  function drifting(): boolean {
    return !calm && !dragging && selected < 0 && pos.length > 0;
  }

  function moveNodes(): void {
    for (let i = 0; i < pos.length; i += 2) {
      const d = i * 3;
      pos[i] =
        (home[i] ?? 0) +
        (drift[d] ?? 0) *
          Math.sin((drift[d + 2] ?? 0) * clock + (drift[d + 4] ?? 0));
      pos[i + 1] =
        (home[i + 1] ?? 0) +
        (drift[d + 1] ?? 0) *
          Math.sin((drift[d + 3] ?? 0) * clock + (drift[d + 5] ?? 0));
    }
    renderer?.setPositions(pos);
  }

  function labelWidth(text: string): number {
    let w = widths.get(text);
    if (w === undefined && labelLayer && measurer) {
      const cs = getComputedStyle(labelLayer);
      measurer.font = `${cs.fontSize} ${cs.fontFamily}`;
      w = measurer.measureText(text).width;
      widths.set(text, w);
    }
    return w ?? 0;
  }

  // Greedy: a label is drawn only if it clears every label already placed this frame.
  // shortcut: label width is measured once per title and placement is a linear scan, so a few hundred labels at most; upgrade to a spatial grid if more.
  function drawLabels(): void {
    const [w, h] = size();
    const placed: { text: string; x: number; y: number }[] = [];
    const boxes: number[] = [];
    const place = (i: number) => {
      if (placed.length >= MAX_LABELS || (i !== selected && !matched[i]))
        return;
      const sx = (pos[2 * i] ?? 0) * cam.zoom + cam.x;
      const sy = (pos[2 * i + 1] ?? 0) * cam.zoom + cam.y;
      if (sx < 0 || sy < 0 || sx > w || sy > h) return;
      const text = data.nodes[i]?.title ?? "";
      const x = sx + (i === selected ? 7 : 4) + LABEL_GAP;
      const y = sy - LABEL_H / 2;
      const x1 = x + labelWidth(text);
      for (let k = 0; k < boxes.length; k += 4) {
        if (
          x < (boxes[k + 2] ?? 0) &&
          x1 > (boxes[k] ?? 0) &&
          y < (boxes[k + 3] ?? 0) &&
          y + LABEL_H > (boxes[k + 1] ?? 0)
        )
          return;
      }
      boxes.push(x, y, x1, y + LABEL_H);
      placed.push({ text, x, y });
    };
    if (selected >= 0) place(selected);
    for (let i = 0; i < data.nodes.length; i++) if (i !== selected) place(i);

    labels = placed;
  }

  function draw(): void {
    frame = 0;
    const now = performance.now();
    // Capped, so a frame after a long pause (or the first frame) does not jump the nodes.
    if (drifting()) {
      clock += Math.min(now - last, 100) / 1000;
      moveNodes();
    }
    last = now;
    if (renderer && colours) renderer.draw(cam, colours.bg, colours.edge);
    drawLabels();
    // Read by the e2e test: how many nodes the last frame placed inside the canvas.
    if (canvas) canvas.dataset.inView = String(countInView());
    if (drifting()) schedule();
  }

  function size(): [number, number] {
    return [canvas?.clientWidth ?? 0, canvas?.clientHeight ?? 0];
  }

  function countInView(): number {
    const [w, h] = size();
    let n = 0;
    for (let i = 0; i < pos.length; i += 2) {
      const sx = (pos[i] ?? 0) * cam.zoom + cam.x;
      const sy = (pos[i + 1] ?? 0) * cam.zoom + cam.y;
      if (sx >= 0 && sy >= 0 && sx <= w && sy <= h) n++;
    }
    return n;
  }

  function fitAll(): void {
    if (!home.length) return;
    let minX = Infinity;
    let minY = Infinity;
    let maxX = -Infinity;
    let maxY = -Infinity;
    for (let i = 0; i < home.length; i += 2) {
      minX = Math.min(minX, home[i] ?? 0);
      maxX = Math.max(maxX, home[i] ?? 0);
      minY = Math.min(minY, home[i + 1] ?? 0);
      maxY = Math.max(maxY, home[i + 1] ?? 0);
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
    // Refit on every size change, so opening the note drawer (which narrows the canvas) keeps the graph in view.
    const fit = () => {
      r.resize(c.clientWidth, c.clientHeight, LOW_POWER.dprCap);
      fitAll();
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
      dragging = true;
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
    const endDrag = () => {
      drag = null;
      dragging = false;
      schedule();
    };
    const onUp = (e: PointerEvent) => {
      if (!drag) return;
      const [x, y] = local(e);
      if (!drag.moved) {
        const hit = hitTest(pos, cam, x, y, 8);
        onselect(hit >= 0 ? (data.nodes[hit]?.id ?? null) : null);
      }
      endDrag();
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
    c.addEventListener("pointercancel", endDrag);
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
    home = layout(data.nodes.length, pairs);
    pos = new Float32Array(home.length);
    pos.set(home);
    drift = driftParams(data.nodes.length);
    const flat = new Uint32Array(pairs.length * 2);
    pairs.forEach(([a, b], i) => {
      flat[2 * i] = a;
      flat[2 * i + 1] = b;
    });
    r.setGraph(pos, flat);
    fitAll();
    pushStyle();
    schedule();
  }

  // Random but fixed per node (seeded), so a relayout drifts the same way each time.
  function driftParams(n: number): Float32Array<ArrayBuffer> {
    const rand = mulberry32(7);
    const out = new Float32Array(n * 6);
    const amp = 2 + 0.6 * Math.sqrt(n);
    for (let i = 0; i < n * 6; i += 6) {
      out[i] = amp * (0.5 + rand());
      out[i + 1] = amp * (0.5 + rand());
      out[i + 2] = 0.04 + 0.08 * rand();
      out[i + 3] = 0.04 + 0.08 * rand();
      out[i + 4] = rand() * Math.PI * 2;
      out[i + 5] = rand() * Math.PI * 2;
    }
    return out;
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
    <div
      class="labels"
      aria-hidden="true"
      bind:this={labelLayer}
      data-labels={labels.length}
    >
      {#each labels as l, k (k)}
        <span class="label" style:transform="translate({l.x}px, {l.y}px)"
          >{l.text}</span
        >
      {/each}
    </div>
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
    display: flex;
    width: 100%;
    height: 100%;
    overflow: hidden;
  }

  .canvas-box {
    position: relative;
    flex: 1;
    min-width: 0;
    height: 100%;
  }

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

  /* Labels are DOM text over the canvas; they never take pointer events, so clicks reach the graph. */
  .labels {
    position: absolute;
    inset: 0;
    overflow: hidden;
    pointer-events: none;
    font-size: var(--font-size-xs);
  }

  .label {
    position: absolute;
    left: 0;
    top: 0;
    white-space: nowrap;
    line-height: 14px;
    color: var(--color-text-muted);
    text-shadow:
      0 0 3px var(--color-bg-0),
      0 0 3px var(--color-bg-0);
  }

  .notice {
    position: absolute;
    inset: 0;
    display: grid;
    place-items: center;
    margin: 0;
    color: var(--color-text-muted);
  }

  /* Beside the canvas, as Obsidian's side panels are, so it never covers the graph. */
  .drawer {
    flex: none;
    width: min(320px, 45%);
    overflow-y: auto;
    padding: var(--space-4);
    background: var(--color-bg-1);
    border-left: 1px solid var(--color-border);
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
