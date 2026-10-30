<script lang="ts">
  import { untrack } from "svelte";
  import { SvelteMap } from "svelte/reactivity";
  import { invoke } from "@tauri-apps/api/core";
  import { hexOf, parse, token } from "./colors";
  import { parseNote, type Block, type Inline } from "./markdown";
  import type { Rgba } from "./renderer";
  import { BrainRenderer } from "./renderer";
  import { Canvas2DRenderer } from "./renderer-canvas";
  import {
    centerOn,
    groupsOf,
    hitTest,
    labelAlpha,
    LOW_POWER,
    linkCounts,
    matchFilter,
    NODE_HIT_PX,
    newSim,
    nodeRadius,
    nodeShape,
    nodeTone,
    SHAPE_DISK,
    tint,
    reheat,
    settle,
    straightLines,
    tick,
    zoomAt,
    incidentLines,
    type Camera,
    type GraphData,
    type Sim,
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
  let labels = $state<{ text: string; x: number; y: number; a: number }[]>([]);
  let hovered = -1;
  let error = $state<string | null>(null);
  let cam = $state<Camera>({ x: 0, y: 0, zoom: 1 });

  // Plain variables: they are rebuilt from `data` and read by the draw loop, not by the template.
  let renderer: BrainRenderer | Canvas2DRenderer | null = null;
  // The live simulation. `pos` is its positions (the notes, then the core at the origin), which are what is drawn and hit-tested.
  let sim: Sim = newSim(0, []);
  let pos: Float32Array<ArrayBuffer> = new Float32Array(0);
  // The world-space segments drawn for the links.
  let lines: Float32Array = new Float32Array(0);
  // Hides notes with no links. Off by default, so every note shows.
  let hideOrphans = $state(false);
  let hideNames = $state(false);
  // Reduced motion: the nodes stay still.
  const calm =
    typeof matchMedia === "function" &&
    matchMedia("(prefers-reduced-motion: reduce)").matches;
  const widths = new SvelteMap<string, number>();
  const measurer = document.createElement("canvas").getContext("2d");
  let colours: {
    node: Rgba;
    tones: Rgba[];
    hot: Rgba;
    edge: Rgba;
    edgeDim: Rgba;
    edgeFocus: Rgba;
    bg: Rgba;
  } | null = null;
  // The hovered (else selected) note, or -1; its links are drawn bright, the rest dim.
  let focusIdx = -1;
  let frame = 0;
  // Group colours the viewer picked in the key; unset groups use the accent. Kept per viewer.
  const PICKS_KEY = "graph-group-colours";
  function loadPicks(): Record<string, string> {
    try {
      return JSON.parse(localStorage.getItem(PICKS_KEY) ?? "{}");
    } catch {
      return {};
    }
  }
  let picks = $state<Record<string, string>>(loadPicks());
  function setPick(name: string, value: string | null): void {
    if (value) picks[name] = value;
    else delete picks[name];
    try {
      localStorage.setItem(PICKS_KEY, JSON.stringify(picks));
    } catch {
      // Storage can be blocked; the pick still applies for this session.
    }
    pushStyle();
  }

  const index = $derived(new Map(data.nodes.map((n, i) => [n.id, i])));
  const selected = $derived(selectedId ? (index.get(selectedId) ?? -1) : -1);
  const matched = $derived(matchFilter(data.nodes, { query, tag, memory }));
  const degree = $derived(linkCounts(data.nodes, data.edges));
  const groups = $derived(groupsOf(data.nodes));
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

  // Links are rebuilt from the node positions whenever those move, so each line follows its two notes.
  // shortcut: every link is rebuilt on each moving frame, which is fine to a few thousand links; upgrade to a dirty flag if more.
  function refreshLines(): void {
    renderer?.setPositions(pos);
    lines = straightLines(pos, sim.edges);
    renderer?.setLines(lines);
    focusEdges();
  }

  // The links of the focused note only, so they can be drawn bright. Follows the note as it moves.
  function focusEdges(): void {
    renderer?.setFocusLines(incidentLines(pos, sim.edges, focusIdx));
  }

  // Hit tests look only at the notes: the group centres and the core sit after them in pos.
  function notes(): Float32Array {
    return pos.subarray(0, 2 * data.nodes.length);
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
    if (hideNames) {
      labels = [];
      return;
    }
    const [w, h] = size();
    const fade = labelAlpha(cam.zoom);
    const placed: { text: string; x: number; y: number; a: number }[] = [];
    const boxes: number[] = [];
    const place = (i: number, a: number) => {
      if (placed.length >= MAX_LABELS || !visible[i] || a <= 0) return;
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
      placed.push({ text, x, y, a });
    };
    // The focused note and its links are always named; every other name fades in with zoom.
    for (const i of near) place(i, 1);
    for (let i = 0; i < data.nodes.length; i++) if (!near.has(i)) place(i, fade);
    labels = placed;
  }

  function draw(): void {
    frame = 0;
    // Live motion: one simulation step a frame while it is still hot. Reduced motion stays still.
    if (!calm && tick(sim)) {
      refreshLines();
      schedule();
    }
    if (renderer && colours)
      renderer.draw(
        cam,
        colours.bg,
        focusIdx >= 0 ? colours.edgeDim : colours.edge,
        colours.edgeFocus,
      );
    drawLabels();
    // Read by the e2e test: how many nodes the last frame placed inside the canvas.
    if (canvas) canvas.dataset.inView = String(countInView());
  }

  function size(): [number, number] {
    return [canvas?.clientWidth ?? 0, canvas?.clientHeight ?? 0];
  }

  function countInView(): number {
    const [w, h] = size();
    let n = 0;
    for (let i = 0; i < 2 * data.nodes.length; i += 2) {
      const sx = (pos[i] ?? 0) * cam.zoom + cam.x;
      const sy = (pos[i + 1] ?? 0) * cam.zoom + cam.y;
      if (sx >= 0 && sy >= 0 && sx <= w && sy <= h) n++;
    }
    return n;
  }

  function fitAll(): void {
    if (!sim.count) return;
    // Every dot fits the view, the core included, so no outlier is cut off.
    let minX = Infinity;
    let maxX = -Infinity;
    let minY = Infinity;
    let maxY = -Infinity;
    for (let i = 0; i < pos.length; i += 2) {
      const x = pos[i] ?? 0;
      const y = pos[i + 1] ?? 0;
      minX = Math.min(minX, x);
      maxX = Math.max(maxX, x);
      minY = Math.min(minY, y);
      maxY = Math.max(maxY, y);
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

  // The notes linked to `i`, and `i` itself. Empty for -1.
  let near = new Set<number>();
  function neighbourhood(i: number): Set<number> {
    const out = new Set<number>();
    if (i < 0) return out;
    out.add(i);
    for (let e = 0; e < sim.edges.length; e += 2) {
      const a = sim.edges[e] ?? 0;
      const b = sim.edges[e + 1] ?? 0;
      if (a === i) out.add(b);
      else if (b === i) out.add(a);
    }
    return out;
  }

  function pushStyle(): void {
    if (!renderer || !colours) return;
    const n = data.nodes.length;
    // pos also holds the core and the group centres after the notes. They are not drawn (radius 0) and not hit (hit tests stop at the notes).
    const total = pos.length / 2;
    const colors = new Float32Array(total * 4);
    const radii = new Float32Array(total);
    const shapes = new Float32Array(total);
    const picked = groups.names.map((name) => (picks[name] ? parse(picks[name]) : null));
    // A hovered note (else the selected one) and its links stay bright; every other note dims.
    const focus = hovered >= 0 ? hovered : selected;
    near = neighbourhood(focus);
    focusIdx = focus;
    focusEdges();
    for (let i = n; i < total; i++) {
      colors.set(colours.node, i * 4);
      radii[i] = 0;
      shapes[i] = SHAPE_DISK;
    }
    for (let i = 0; i < n; i++) {
      const isSel = i === selected;
      const tone = colours.tones[nodeTone(data.nodes[i]?.id ?? "")] ?? colours.node;
      const base = isSel ? colours.hot : (picked[groups.of[i] ?? 0] ?? tone);
      const lit = focus < 0 || near.has(i) ? 1 : 0.2;
      const alpha = visible[i] ? base[3] * lit : base[3] * 0.15;
      colors.set([base[0], base[1], base[2], alpha], i * 4);
      radii[i] = nodeRadius(degree[i] ?? 0, isSel);
      shapes[i] = nodeShape(data.nodes[i]?.id ?? "");
    }
    renderer.setColors(colors);
    renderer.setRadii(radii);
    renderer.setShapes(shapes);
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
      // Note outlines: the accent, then two lighter tints of it (see nodeTone in model.ts).
      tones: [0, 0.3, 0.55].map((t) => tint(token("accent"), t) as Rgba),
      hot: token("confirm"),
      edge: [...token("link").slice(0, 3), 0.16] as Rgba,
      edgeDim: [...token("link").slice(0, 3), 0.04] as Rgba,
      edgeFocus: [...token("link").slice(0, 3), 0.7] as Rgba,
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

    // `node` is the note grabbed at pointer-down, or -1 for a pan of the whole graph.
    let drag: {
      x: number;
      y: number;
      cam: Camera;
      moved: boolean;
      node: number;
    } | null = null;
    const local = (e: PointerEvent | WheelEvent) => {
      const rect = c.getBoundingClientRect();
      return [e.clientX - rect.left, e.clientY - rect.top] as const;
    };
    const onDown = (e: PointerEvent) => {
      c.setPointerCapture(e.pointerId);
      const [x, y] = local(e);
      const hit = hitTest(notes(), cam, x, y, NODE_HIT_PX);
      // Every dot can be dragged, including the ones a filter has dimmed.
      const node = hit;
      // A grabbed note is pinned under the pointer; its neighbours are pulled along by the simulation.
      sim.grabbed = node;
      drag = { x, y, cam, moved: false, node };
      if (node >= 0) reheat(sim);
      schedule();
    };
    const onMove = (e: PointerEvent) => {
      if (!drag) {
        // Hover lights the note and its links, and names them.
        const [hx, hy] = local(e);
        const hit = hitTest(notes(), cam, hx, hy, NODE_HIT_PX);
        const next = hit >= 0 && visible[hit] ? hit : -1;
        if (next !== hovered) {
          hovered = next;
          pushStyle();
        }
        return;
      }
      const [x, y] = local(e);
      const dx = x - drag.x;
      const dy = y - drag.y;
      if (Math.abs(dx) + Math.abs(dy) > 4) drag.moved = true;
      if (drag.node >= 0) {
        pos[2 * drag.node] = (x - cam.x) / cam.zoom;
        pos[2 * drag.node + 1] = (y - cam.y) / cam.zoom;
        reheat(sim);
        refreshLines();
      } else {
        cam = { ...drag.cam, x: drag.cam.x + dx, y: drag.cam.y + dy };
      }
      schedule();
    };
    const endDrag = () => {
      // The dropped note is free again, and the simulation re-heats so it settles back among its neighbours.
      sim.grabbed = -1;
      if (drag?.node !== undefined && drag.node >= 0) reheat(sim);
      drag = null;
      schedule();
    };
    const onUp = (e: PointerEvent) => {
      if (!drag) return;
      const [x, y] = local(e);
      if (!drag.moved) {
        const hit = hitTest(notes(), cam, x, y, NODE_HIT_PX);
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

  // A fresh simulation, settled before the first frame. Dragged notes go back to it too.
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
    sim = newSim(data.nodes.length, pairs);
    settle(sim, LOW_POWER.iterations);
    pos = sim.pos;
    lines = straightLines(pos, sim.edges);
    r.setGraph(pos, lines);
    fitAll();
    pushStyle();
  }

  // Re-colour when the filter or the selection changes.
  $effect(() => {
    void visible;
    void selected;
    void hideNames;
    pushStyle();
    schedule();
  });

  // Obsidian's keys: +/- zoom about the middle, arrows move the view (Shift for a bigger step). Not while typing.
  function onWindowKey(e: KeyboardEvent): void {
    if (e.key === "Escape" && selected >= 0) return onselect(null);
    const target = e.target instanceof HTMLElement ? e.target : null;
    if (target?.closest("input, textarea, select, [contenteditable]")) return;
    const [w, h] = size();
    const step = e.shiftKey ? 160 : 40;
    const moves: Record<string, [number, number]> = {
      ArrowLeft: [-step, 0],
      ArrowRight: [step, 0],
      ArrowUp: [0, -step],
      ArrowDown: [0, step],
    };
    const move = moves[e.key];
    if (e.key === "+" || e.key === "=") cam = zoomAt(cam, w / 2, h / 2, 1.25);
    else if (e.key === "-" || e.key === "_") cam = zoomAt(cam, w / 2, h / 2, 0.8);
    else if (move) cam = { ...cam, x: cam.x + move[0], y: cam.y + move[1] };
    else return;
    e.preventDefault();
    schedule();
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
        <span class="label" style:opacity={l.a} style:transform="translate({l.x}px, {l.y}px)"
          >{l.text}</span
        >
      {/each}
    </div>
  </div>

  <div class="tools">
    <button type="button" class="fit" onclick={fitAll}>Fit graph</button>
    <label class="toggle">
      <input type="checkbox" bind:checked={hideOrphans} /> Hide orphans
    </label>
    <label class="toggle">
      <input type="checkbox" bind:checked={hideNames} /> Hide names
    </label>
  </div>

  {#if groups.names.length}
    <ul class="key" aria-label="Key: group colours">
      <li class="key-title">Key</li>
      {#each groups.names as name (name)}
        <li>
          <input
            type="color"
            class="pick"
            aria-label="Colour for {name}"
            value={picks[name] ?? hexOf(colours?.node ?? [0, 0, 0, 1])}
            onchange={(e) => setPick(name, e.currentTarget.value)}
          />{name}
          {#if picks[name]}
            <button class="reset" type="button" onclick={() => setPick(name, null)}>reset</button>
          {/if}
        </li>
      {/each}
    </ul>
  {/if}

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

  /* The arc layout's group key, under the tools, top left. */
  .key {
    position: absolute;
    top: calc(var(--space-2) + 40px);
    left: var(--space-2);
    z-index: 1;
    margin: 0;
    padding: 0;
    list-style: none;
    max-height: 60%;
    overflow-y: auto;
    font-size: var(--font-size-xs);
    line-height: 16px;
    color: var(--color-text-muted);
    pointer-events: none;
  }

  .key-title {
    color: var(--color-text);
    margin-bottom: var(--space-1);
  }

  /* 44px touch target; the padding keeps the visible swatch at 12px, and the negative margin keeps the row height. */
  .pick {
    box-sizing: border-box;
    box-sizing: border-box;
    width: 44px;
    height: 44px;
    padding: 16px;
    margin: -16px var(--space-2) -16px -16px;
    border: none;
    background: none;
    vertical-align: middle;
    pointer-events: auto;
    cursor: pointer;
  }

  .reset {
    margin-left: var(--space-2);
    padding: 0;
    border: none;
    background: none;
    color: var(--color-link);
    font: inherit;
    pointer-events: auto;
    cursor: pointer;
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

  /* Tablets and touch screens: the toggle labels are the touch target, so they take the minimum height. */
  @media (max-width: 1100px), (pointer: coarse) {
    .toggle {
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
