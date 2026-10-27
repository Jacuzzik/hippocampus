<script lang="ts">
  import { untrack } from "svelte";
  import { SvelteMap } from "svelte/reactivity";
  import { invoke } from "@tauri-apps/api/core";
  import { token } from "./colors";
  import { parseNote, type Block, type Inline } from "./markdown";
  import type { Rgba } from "./renderer";
  import { BrainRenderer } from "./renderer";
  import { Canvas2DRenderer } from "./renderer-canvas";
  import {
    centerOn,
    hitTest,
    LOW_POWER,
    layout,
    linkCounts,
    matchFilter,
    mulberry32,
    nodeRadius,
    zoomAt,
    type Camera,
    type GraphData,
  } from "./model";

  const LABEL_GAP = 4;
  const LABEL_H = 14;
  const MAX_LABELS = 300;

  // The note list in the sidebar owns the search, tag and memory filters and selection; the graph draws them.
  let {
    data,
    query = "",
    tag = null,
    memory = false,
    selectedId = null,
    onselect,
  }: {
    data: GraphData;
    query?: string;
    tag?: string | null;
    memory?: boolean;
    selectedId?: string | null;
    onselect: (id: string | null) => void;
  } = $props();

  let canvas: HTMLCanvasElement | undefined = $state();
  let labelLayer: HTMLDivElement | undefined = $state();
  let labels = $state<{ text: string; x: number; y: number }[]>([]);
  let hovered = -1;
  let error = $state<string | null>(null);
  let cam = $state<Camera>({ x: 0, y: 0, zoom: 1 });

  // Plain variables: they are rebuilt from `data` and read by the draw loop, not by the template.
  let renderer: BrainRenderer | Canvas2DRenderer | null = null;
  // `home` is the laid-out position; `pos` is home plus the drift, and is what is drawn and hit-tested.
  let home: Float32Array<ArrayBuffer> = new Float32Array(0);
  let pos: Float32Array<ArrayBuffer> = new Float32Array(0);
  // Per node: x and y drift amplitude, x and y angular speed, x and y phase. Six floats each.
  let drift: Float32Array<ArrayBuffer> = new Float32Array(0);
  let clock = 0;
  let last = 0;
  let dragging = false;
  // Hides notes with no links. Off by default, so every note shows.
  let hideOrphans = $state(false);
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
  const matched = $derived(matchFilter(data.nodes, { query, tag, memory }));
  const degree = $derived(linkCounts(data.nodes, data.edges));
  const visible = $derived(
    matched.map((m, i) => m && !(hideOrphans && degree[i] === 0)),
  );
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
      if (placed.length >= MAX_LABELS || i !== hovered || !visible[i]) return;
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
    if (hovered >= 0) place(hovered);

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

  // [[Name]] links match a note's title or its file name, as the vault's own link rules do.
  function resolve(target: string): string | null {
    const key = target.replace(/\.md$/i, "").toLowerCase();
    const hit = data.nodes.find((n) => {
      const stem = n.id.replace(/\.md$/i, "").toLowerCase();
      return (
        n.title.toLowerCase() === key ||
        stem === key ||
        stem.endsWith(`/${key}`)
      );
    });
    return hit?.id ?? null;
  }

  // The body is read from the sidecar when the drawer opens on a note. A reply for an earlier note is dropped.
  let body = $state<
    { id: string; blocks: Block[] } | { id: string; error: string } | null
  >(null);
  $effect(() => {
    const id = node?.id;
    if (!id) return;
    let stale = false;
    invoke<{ text: string }>("sidecar_call", {
      method: "read",
      params: { path: id },
    })
      .then((answer) => {
        if (!stale) body = { id, blocks: parseNote(answer.text) };
      })
      .catch((cause: unknown) => {
        if (!stale) body = { id, error: String(cause) };
      });
    return () => {
      stale = true;
    };
  });
  const shown = $derived(body && node && body.id === node.id ? body : null);

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
      const alpha = visible[i] ? base[3] : base[3] * 0.15;
      colors.set([base[0], base[1], base[2], alpha], i * 4);
      radii[i] = nodeRadius(degree[i] ?? 0, isSel);
    }
    renderer.setColors(colors);
    renderer.setRadii(radii);
    schedule();
  }

  // Phones and some browsers have no WebGL 2; the 2D canvas draws the same graph instead.
  function createRenderer(
    c: HTMLCanvasElement,
  ): BrainRenderer | Canvas2DRenderer {
    try {
      return new BrainRenderer(c);
    } catch (cause) {
      console.warn(
        "WebGL 2 unavailable; drawing the graph on a 2D canvas",
        cause,
      );
      return new Canvas2DRenderer(c);
    }
  }

  // Create the renderer once per canvas and keep the canvas size in step with its box.
  $effect(() => {
    const c = canvas;
    if (!c) return;
    let r: BrainRenderer | Canvas2DRenderer;
    try {
      r = createRenderer(c);
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
      if (!drag) {
        // Labels show only for the node under the pointer.
        const [hx, hy] = local(e);
        const hit = hitTest(pos, cam, hx, hy, 8);
        const next = hit >= 0 && visible[hit] ? hit : -1;
        if (next !== hovered) {
          hovered = next;
          schedule();
        }
        return;
      }
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
        const id = hit >= 0 && visible[hit] ? data.nodes[hit]?.id : undefined;
        onselect(id ?? null);
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
    void visible;
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

  <div class="tools">
    <button type="button" class="fit" onclick={fitAll}>Fit graph</button>
    <label class="orphans">
      <input type="checkbox" bind:checked={hideOrphans} /> Hide orphans
    </label>
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
      <section class="body" aria-label="Note text">
        {#if shown && "error" in shown}
          <p class="muted" role="alert">
            Could not read this note: {shown.error}
          </p>
        {:else if shown}
          <!-- A leading title heading repeats the drawer's own title, so it is not shown twice. -->
          {#each shown.blocks.filter((b, k) => !(k === 0 && b.kind === "heading" && b.level === 1 && b.children
                  .map((c) => c.text)
                  .join("") === node?.title)) as block, k (k)}
            {#if block.kind === "heading"}
              <svelte:element this={`h${block.level}`}>
                {@render inlines(block.children)}
              </svelte:element>
            {:else if block.kind === "paragraph"}
              <p>{@render inlines(block.children)}</p>
            {:else if block.kind === "list"}
              <svelte:element this={block.ordered ? "ol" : "ul"} class="items">
                {#each block.items as item, j (j)}
                  <li>{@render inlines(item)}</li>
                {/each}
              </svelte:element>
            {:else}
              <pre><code>{block.text}</code></pre>
            {/if}
          {/each}
        {:else}
          <p class="muted">Loading the note…</p>
        {/if}
      </section>
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

{#snippet inlines(parts: Inline[])}
  {#each parts as part, k (k)}
    {#if part.kind === "code"}<code>{part.text}</code>
    {:else if part.kind === "strong"}<strong>{part.text}</strong>
    {:else if part.kind === "em"}<em>{part.text}</em>
    {:else if part.kind === "link"}<a href={part.href} rel="noopener noreferrer"
        >{part.text}</a
      >
    {:else if part.kind === "wiki"}
      {@const id = resolve(part.target)}
      {#if id}<button type="button" class="wiki" onclick={() => open(id)}
          >{part.text}</button
        >
      {:else}<span class="wiki-missing">{part.text}</span>{/if}
    {:else}{part.text}{/if}
  {/each}
{/snippet}

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

  /* Top left, clear of the drawer on the right. */
  .tools {
    position: absolute;
    top: var(--space-2);
    left: var(--space-2);
    z-index: 1;
    display: flex;
    align-items: center;
    gap: var(--space-2);
    font-size: var(--font-size-xs);
    color: var(--color-text-muted);
  }

  .fit {
    font: inherit;
    font-size: var(--font-size-xs);
    color: var(--color-text);
    background: var(--color-bg-1);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    padding: var(--space-1) var(--space-2);
    cursor: pointer;
  }

  /* Tablets and touch screens: the Hide orphans label is the touch target, so it takes the minimum height. */
  @media (max-width: 1100px), (pointer: coarse) {
    .orphans {
      display: inline-flex;
      align-items: center;
      min-height: var(--layout-touch-target);
    }
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

  .body {
    margin-top: var(--space-3);
    font-size: var(--font-size-sm);
    line-height: 1.6;
  }

  .body p {
    margin: var(--space-2) 0 0;
  }

  .body h1,
  .body h2,
  .body h3,
  .body h4,
  .body h5,
  .body h6 {
    margin: var(--space-3) 0 0;
    font-size: var(--font-size-sm);
  }

  .body .items {
    margin-left: var(--space-4);
    list-style: revert;
  }

  .body .items li + li {
    margin-top: 0;
  }

  .body pre {
    margin: var(--space-2) 0 0;
    padding: var(--space-2);
    overflow-x: auto;
    background: var(--color-surface);
    border-radius: var(--radius-sm);
    font-size: var(--font-size-xs);
  }

  .body code {
    font-family: var(--font-mono);
  }

  .body a {
    color: var(--color-link);
  }

  .wiki {
    display: inline;
    color: var(--color-link);
    text-decoration: underline;
  }

  .wiki-missing {
    color: var(--color-text-muted);
  }
</style>
