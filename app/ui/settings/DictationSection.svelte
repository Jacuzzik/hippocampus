<script lang="ts">
  import { onMount } from "svelte";
  import Button from "../controls/Button.svelte";
  import { call } from "./call";

  // 7.27: dictation with a program on this computer. Nothing is sent anywhere and nothing is downloaded.
  type State = {
    ready: boolean;
    recorder: string | null;
    engine: string | null;
    typer: string | null;
    copier: string | null;
    missing: { what: string; how: string }[];
    mode: "type" | "copy";
    hotkey: string;
    configured_model: string;
    model: string;
    recording: boolean;
  };
  let view = $state<State | null>(null);
  let mode = $state<"type" | "copy">("type");
  let model = $state("");
  let error = $state("");
  let done = $state("");
  let busy = $state(false);

  async function act(fn: () => Promise<void>): Promise<void> {
    busy = true;
    error = "";
    try {
      await fn();
    } catch (cause) {
      error = String(cause);
    } finally {
      busy = false;
    }
  }
  function setView(next: State): void {
    view = next;
    mode = next.mode;
    model = next.configured_model;
  }
  onMount(
    () => void act(async () => setView(await call<State>("dictation_state"))),
  );
</script>

<section class="control-section" aria-labelledby="dictation-title">
  <h3 id="dictation-title">Dictation</h3>
  <p class="hint">
    Press Ctrl+Shift+D, speak, and press it again: your words are typed where
    your cursor is. It uses a speech-to-text program on this computer, so
    nothing is sent anywhere and no model is downloaded. The recording is
    deleted as soon as it is turned into text.
  </p>
  {#if view}
    <p>
      {view.ready
        ? `Ready: ${view.engine} with ${view.recorder}.`
        : "Not set up yet."}
    </p>
    {#if view.missing.length}
      <ul aria-label="What to install">
        {#each view.missing as item (item.what)}
          <li><strong>{item.what}.</strong> {item.how}</li>
        {/each}
      </ul>
    {/if}
    <label>
      Speech model file (whisper.cpp)
      <input bind:value={model} placeholder="/path/to/ggml-base.en.bin" />
    </label>
    <label>
      The text goes
      <select bind:value={mode}>
        <option value="type"
          >Typed into the app in front ({view.typer ??
            "no typing program found"})</option
        >
        <option value="copy"
          >Copied to the clipboard ({view.copier ??
            "no clipboard program found"})</option
        >
      </select>
    </label>
    <div class="row">
      <Button
        disabled={busy}
        onclick={() =>
          void act(async () =>
            setView(await call<State>("dictation_set", { mode, model })),
          )}>Save</Button
      >
      <Button
        disabled={busy || !view.ready}
        onclick={() =>
          void act(async () => {
            await call("dictation_start");
            done = "Listening. Press Stop and show text when you finish.";
          })}>Test: start listening</Button
      >
      <Button
        disabled={busy || !view.ready}
        onclick={() =>
          void act(async () => {
            const r = await call<{ text: string; did: string }>(
              "dictation_stop",
            );
            done = r.text ? `You said: ${r.text}` : r.did;
          })}>Stop and show text</Button
      >
    </div>
    {#if done}<p>{done}</p>{/if}
  {/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>

<style>
  .row {
    display: flex;
    gap: var(--space-2);
    flex-wrap: wrap;
    margin-top: var(--space-2);
  }
  label {
    display: block;
    margin-top: var(--space-2);
  }
  input {
    width: 100%;
  }
</style>
