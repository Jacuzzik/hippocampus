<script lang="ts">
  // The Phone dashboard: every Android device adb sees, side by side, each with its live screen.
  // "Show here" streams the screen into the app (core/phone_view.py). A click on the picture taps the
  // phone, a drag swipes it, and the buttons under it press Back, Home and Recent apps or type text,
  // all through adb (core/phone.py control). "Own window" opens scrcpy's window. Each click is the approval.
  // Agents use the same phones with adb; their start-up inbox lists them.
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import EmptyState from "../controls/EmptyState.svelte";
  import ErrorRow from "../controls/ErrorRow.svelte";
  import Loading from "../controls/Loading.svelte";

  type Phone = {
    adb: boolean;
    scrcpy: boolean;
    devices: { serial: string; state: string; model: string }[];
    mirroring: string[];
    showing?: Record<string, string>;
    error: string;
  };
  type Action =
    | { kind: "tap"; x: number; y: number; landscape: boolean }
    | {
        kind: "swipe";
        x: number;
        y: number;
        x2: number;
        y2: number;
        ms: number;
        landscape: boolean;
      }
    | { kind: "key"; key: string }
    | { kind: "text"; text: string };

  let phone = $state<Phone | null>(null);
  let error = $state<string | null>(null);
  let actionError = $state<string | null>(null);
  let busy = $state<string | null>(null);
  let typed = $state<Record<string, string>>({});

  async function read(): Promise<void> {
    error = null;
    try {
      phone = await invoke<Phone>("sidecar_call", { method: "phone_status" });
    } catch (cause) {
      error = String(cause);
    }
  }
  onMount(() => void read());

  async function act(method: string, serial: string): Promise<void> {
    actionError = null;
    busy = serial;
    try {
      phone = await invoke<Phone>("sidecar_call", {
        method,
        params: { serial, approve: true },
      });
    } catch (cause) {
      actionError = String(cause);
    } finally {
      busy = null;
    }
  }

  async function control(serial: string, action: Action): Promise<void> {
    actionError = null;
    try {
      await invoke("sidecar_call", {
        method: "phone_control",
        params: { serial, action, approve: true },
      });
    } catch (cause) {
      actionError = String(cause);
    }
  }

  // The window's picture tag shows only the first frame of a multipart stream, so the stream is read
  // here and each whole JPEG frame is put into the picture as it arrives.
  function live(img: HTMLImageElement, url: string) {
    const stop = new AbortController();
    let shown = "";
    const put = (bytes: Uint8Array): void => {
      const next = URL.createObjectURL(
        new Blob([bytes.slice().buffer], { type: "image/jpeg" }),
      );
      img.src = next;
      if (shown) URL.revokeObjectURL(shown);
      shown = next;
    };
    async function run(): Promise<void> {
      if (!url.startsWith("http")) {
        img.src = url; // a still picture (the test stand-in)
        return;
      }
      const reply = await fetch(url, { signal: stop.signal });
      const reader = reply.body?.getReader();
      if (!reader) return;
      let buffer = new Uint8Array(0);
      for (;;) {
        const { value, done } = await reader.read();
        if (done) return;
        const joined = new Uint8Array(buffer.length + value.length);
        joined.set(buffer);
        joined.set(value, buffer.length);
        buffer = joined;
        // Keep only the newest whole picture: FFD8 starts one, FFD9 ends it.
        let start = -1;
        let end = -1;
        for (let i = buffer.length - 2; i >= 0; i--) {
          if (end < 0 && buffer[i] === 0xff && buffer[i + 1] === 0xd9)
            end = i + 2;
          if (end > 0 && buffer[i] === 0xff && buffer[i + 1] === 0xd8) {
            start = i;
            break;
          }
        }
        if (start >= 0 && end > start) {
          put(buffer.slice(start, end));
          buffer = buffer.slice(end);
        }
      }
    }
    void run().catch(() => {});
    return {
      destroy() {
        stop.abort();
        if (shown) URL.revokeObjectURL(shown);
      },
    };
  }

  // A press and release in the same spot is a tap; a press that moves is a swipe.
  let pressed: { x: number; y: number; at: number } | null = null;
  function spot(event: PointerEvent): {
    x: number;
    y: number;
    landscape: boolean;
  } {
    const img = event.currentTarget as HTMLImageElement;
    const box = img.getBoundingClientRect();
    const clamp = (n: number): number => Math.min(1, Math.max(0, n));
    return {
      x: clamp((event.clientX - box.left) / box.width),
      y: clamp((event.clientY - box.top) / box.height),
      landscape: img.naturalWidth > img.naturalHeight,
    };
  }
  function down(event: PointerEvent): void {
    const at = spot(event);
    pressed = { x: at.x, y: at.y, at: performance.now() };
  }
  function up(event: PointerEvent, serial: string): void {
    if (!pressed) return;
    const at = spot(event);
    const moved = Math.hypot(at.x - pressed.x, at.y - pressed.y) > 0.02;
    const ms = Math.round(
      Math.min(5000, Math.max(80, performance.now() - pressed.at)),
    );
    void control(
      serial,
      moved
        ? {
            kind: "swipe",
            x: pressed.x,
            y: pressed.y,
            x2: at.x,
            y2: at.y,
            ms,
            landscape: at.landscape,
          }
        : { kind: "tap", x: at.x, y: at.y, landscape: at.landscape },
    );
    pressed = null;
  }

  function send(event: SubmitEvent, serial: string): void {
    event.preventDefault();
    const text = typed[serial]?.trim();
    if (!text) return;
    void control(serial, { kind: "text", text });
    typed[serial] = "";
  }

  const STATES: Record<string, string> = {
    device: "Ready",
    unauthorized: "Accept the USB debugging prompt on the phone",
    offline: "Offline",
  };
</script>

{#if error}
  <ErrorRow message={error} onretry={read} />
{:else if phone === null}
  <Loading what="phones" />
{:else}
  <p class="tools">
    adb: <b>{phone.adb ? "installed" : "not installed"}</b> · scrcpy:
    <b>{phone.scrcpy ? "installed" : "not installed"}</b> · agents can use every
    ready phone with adb
    <button type="button" class="small" onclick={read}>Look again</button>
  </p>
  {#if phone.error}<p class="error" role="alert">{phone.error}</p>{/if}
  {#if actionError}<p class="error" role="alert">{actionError}</p>{/if}
  {#if phone.adb && !phone.error && phone.devices.length === 0}
    <EmptyState
      title="No phone is connected"
      text="Plug an Android phone in by USB and turn on USB debugging in its developer options, then press Look again."
    />
  {/if}
  <ul class="devices">
    {#each phone.devices as device (device.serial)}
      {@const shown = phone.showing?.[device.serial]}
      {@const live_ = phone.mirroring.includes(device.serial) || !!shown}
      {@const ready = device.state === "device"}
      <li class="device">
        <div class="head">
          <span class="name">
            <b>{device.model || device.serial}</b>
            <span class="muted"
              >{device.serial} · {STATES[device.state] ?? device.state}{live_
                ? " · mirroring"
                : ""}</span
            >
          </span>
        </div>
        <div class="screen" class:on={!!shown}>
          {#if shown}
            <img
              use:live={shown}
              alt="Screen of {device.model || device.serial}"
              draggable="false"
              onpointerdown={down}
              onpointerup={(event) => up(event, device.serial)}
            />
          {:else}
            <span class="off">
              {ready
                ? "Press Show here to see the screen live."
                : (STATES[device.state] ?? device.state)}
            </span>
          {/if}
        </div>
        {#if shown}
          <div class="keys" role="group" aria-label="Phone buttons">
            <button
              type="button"
              onclick={() =>
                control(device.serial, { kind: "key", key: "back" })}
              >Back</button
            >
            <button
              type="button"
              onclick={() =>
                control(device.serial, { kind: "key", key: "home" })}
              >Home</button
            >
            <button
              type="button"
              onclick={() =>
                control(device.serial, { kind: "key", key: "recents" })}
              >Recent apps</button
            >
          </div>
          <form class="type" onsubmit={(event) => send(event, device.serial)}>
            <input
              type="text"
              maxlength="500"
              aria-label="Type on {device.model || device.serial}"
              placeholder="Type on the phone, then press Enter"
              bind:value={typed[device.serial]}
            />
          </form>
        {/if}
        <div class="actions">
          {#if !shown}
            <button
              type="button"
              class="primary"
              disabled={!phone.scrcpy || !ready || busy === device.serial}
              onclick={() => act("phone_view", device.serial)}
              >{busy === device.serial ? "Starting…" : "Show here"}</button
            >
          {/if}
          {#if !phone.mirroring.includes(device.serial)}
            <button
              type="button"
              disabled={!phone.scrcpy || !ready || busy === device.serial}
              onclick={() => act("phone_mirror", device.serial)}
              >Own window</button
            >
          {/if}
          {#if live_}
            <button
              type="button"
              disabled={busy === device.serial}
              onclick={() => act("phone_stop", device.serial)}
              >Stop mirroring</button
            >
          {/if}
        </div>
      </li>
    {/each}
  </ul>
  {#if phone.devices.length}
    <p class="muted">
      Click the screen to tap, drag to swipe. Own window opens scrcpy in its own
      window. Both use a small size and no sound, so a weak computer copes.
    </p>
  {/if}
{/if}

<style>
  .tools,
  .muted {
    color: var(--color-text-muted);
  }

  .tools {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1) var(--space-2);
    align-items: center;
    margin-top: var(--space-3);
  }

  .tools b {
    color: var(--color-text);
    font-weight: normal;
  }

  /* Phones side by side: as many columns as fit, each one phone wide. */
  .devices {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(var(--size-280), 1fr));
    gap: var(--space-3);
    margin: var(--space-3) 0;
    padding: 0;
    list-style: none;
  }

  .device {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    padding: var(--space-3);
    background: var(--pop-bg);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
  }

  .name {
    display: flex;
    flex-direction: column;
    gap: var(--space-0);
    min-width: 0;
    overflow-wrap: anywhere;
  }

  .screen {
    display: grid;
    place-items: center;
    min-height: var(--size-240);
    padding: var(--space-2);
    background: var(--color-bg-0);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
  }

  .screen img {
    display: block;
    max-width: 100%;
    max-height: 62vh;
    border-radius: var(--radius-sm);
    cursor: pointer;
    touch-action: none;
    user-select: none;
  }

  .off {
    max-width: 24ch;
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
    text-align: center;
  }

  .keys,
  .actions {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
  }

  .keys button {
    flex: 1;
  }

  .type input {
    width: 100%;
  }

  button {
    min-height: var(--size-28);
    padding: var(--space-1) var(--space-3);
    color: var(--color-text);
    font: inherit;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    cursor: pointer;
  }

  button.primary {
    color: var(--color-accent-on);
    background: var(--color-accent);
    border-color: var(--color-accent);
  }

  button.small {
    min-height: var(--size-24);
    padding: 0 var(--space-2);
    font-size: var(--font-size-xs);
  }

  button:hover:not(:disabled) {
    border-color: var(--color-accent);
  }

  button:disabled {
    cursor: default;
    opacity: 0.5;
  }

  .error {
    color: var(--color-danger);
  }
</style>
