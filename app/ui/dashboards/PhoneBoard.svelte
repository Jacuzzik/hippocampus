<script lang="ts">
  // The Phone dashboard: Android devices seen by adb, and screen mirroring with scrcpy.
  // "Show here" puts the screen inside the app (view only, core/phone_view.py); "Own window" opens
  // scrcpy's window, which takes taps and keys. Each click is the approval.
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
  let phone = $state<Phone | null>(null);
  let error = $state<string | null>(null);
  let actionError = $state<string | null>(null);
  let busy = $state<string | null>(null);

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
    <b>{phone.scrcpy ? "installed" : "not installed"}</b>
  </p>
  {#if phone.error}<p class="error" role="alert">{phone.error}</p>{/if}
  {#if phone.adb && !phone.error && phone.devices.length === 0}
    <EmptyState
      title="No phone is connected"
      text="Plug an Android phone in by USB and turn on USB debugging in its developer options, then press Refresh."
    />
  {/if}
  <ul class="devices">
    {#each phone.devices as device (device.serial)}
      {@const shown = phone.showing?.[device.serial]}
      {@const live = phone.mirroring.includes(device.serial) || !!shown}
      <li>
        <span class="name">
          <b>{device.model || device.serial}</b>
          <span class="muted"
            >{device.serial} · {STATES[device.state] ?? device.state}{live
              ? " · mirroring"
              : ""}</span
          >
        </span>
        {#if live}
          <button
            type="button"
            disabled={busy === device.serial}
            onclick={() => act("phone_stop", device.serial)}
            >Stop mirroring</button
          >
        {/if}
        {#if !shown}
          <button
            type="button"
            disabled={!phone.scrcpy ||
              device.state !== "device" ||
              busy === device.serial}
            onclick={() => act("phone_view", device.serial)}
            >{busy === device.serial ? "Starting…" : "Show here"}</button
          >
        {/if}
        {#if !phone.mirroring.includes(device.serial)}
          <button
            type="button"
            disabled={!phone.scrcpy ||
              device.state !== "device" ||
              busy === device.serial}
            onclick={() => act("phone_mirror", device.serial)}
            >Own window</button
          >
        {/if}
      </li>
      {#if shown}
        <li class="screen">
          <img src={shown} alt="Screen of {device.model || device.serial}" />
        </li>
      {/if}
    {/each}
  </ul>
  {#if actionError}<p class="error" role="alert">{actionError}</p>{/if}
  {#if phone.devices.length}
    <p class="muted">
      Show here puts the screen inside the app to watch; it changes only when
      the phone's screen does. Own window opens scrcpy, where you can tap and
      type. Both use a small size and no sound.
    </p>
  {/if}
{/if}

<style>
  .tools,
  .muted {
    color: var(--color-text-muted);
  }

  .tools {
    margin-top: var(--space-3);
  }

  .tools b {
    color: var(--color-text);
    font-weight: normal;
  }

  .devices {
    display: grid;
    gap: var(--space-2);
    margin: var(--space-3) 0;
    padding: 0;
    list-style: none;
  }

  .devices li {
    display: flex;
    gap: var(--space-3);
    align-items: center;
    justify-content: space-between;
    padding: var(--space-3);
    background: var(--color-bg-1);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
  }

  .devices li.screen {
    justify-content: center;
    padding: var(--space-2);
    background: var(--color-bg-0);
  }

  .screen img {
    display: block;
    max-width: 100%;
    max-height: 70vh;
    border-radius: var(--radius-sm);
  }

  .name {
    display: flex;
    flex-direction: column;
    gap: var(--space-0);
    min-width: 0;
    overflow-wrap: anywhere;
    /* The name takes the free space, so the buttons sit together at the right on every row. */
    flex: 1;
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

  button:disabled {
    cursor: default;
    opacity: 0.5;
  }

  .error {
    color: var(--color-danger);
  }
</style>
