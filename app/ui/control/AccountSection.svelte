<script lang="ts">
  import Toggle from "../controls/Toggle.svelte";
  import { invoke } from "@tauri-apps/api/core";
  import { onDestroy, onMount } from "svelte";

  // The Hippocampus account (14.11, M.22). Hidden until this build has the sign-in service set up;
  // the app works fully without an account (14.08).
  type Consent = { sync: boolean; usage: boolean; asked: boolean };
  type Status = {
    configured: boolean;
    signed_in: boolean;
    waiting: boolean;
    consent: Consent;
    offline?: boolean;
    email?: string;
    name?: string;
    plan?: string;
    problem?: string;
  };

  let status = $state<Status | null>(null);
  let error = $state<string | null>(null);
  let busy = $state(false);
  let confirmDelete = $state(false);
  let sync = $state(false);
  let usage = $state(false);
  let timer: ReturnType<typeof setInterval> | undefined;

  async function call(method: string, params?: object): Promise<void> {
    error = null;
    try {
      status = await invoke<Status>("sidecar_call", { method, params });
      sync = status.consent.sync;
      usage = status.consent.usage;
    } catch (cause) {
      error = String(cause);
    }
  }

  // While the browser sign-in is open, look every two seconds for it to finish.
  $effect(() => {
    if (status?.waiting && !timer) {
      timer = setInterval(() => void call("user_account"), 2000);
    } else if (!status?.waiting && timer) {
      clearInterval(timer);
      timer = undefined;
    }
  });
  onDestroy(() => clearInterval(timer));

  async function signIn(): Promise<void> {
    busy = true;
    error = null;
    try {
      await invoke("sidecar_call", { method: "user_sign_in" });
      await call("user_account");
    } catch (cause) {
      error = String(cause);
    } finally {
      busy = false;
    }
  }

  async function run(method: string, params?: object): Promise<void> {
    busy = true;
    await call(method, params);
    busy = false;
    confirmDelete = false;
  }

  onMount(() => void call("user_account"));
</script>

{#if status?.configured}
  <section class="control-section" aria-labelledby="control-account">
    <h3 id="control-account">Account</h3>
    {#if !status.signed_in}
      <p class="hint">
        Optional. Sign in for update notices and your plan. Your notes and
        agents stay on this computer either way.
      </p>
      {#if status.waiting}
        <p class="muted" role="status">
          Finish signing in in your browser, then come back here.
        </p>
        <button type="button" onclick={() => run("user_sign_in_cancel")}
          >Cancel</button
        >
      {:else}
        <button type="button" disabled={busy} onclick={signIn}
          >Sign in with Google</button
        >
      {/if}
    {:else}
      <p>
        <b>{status.name || status.email}</b>
        {#if status.name}<span class="muted">{status.email}</span>{/if}
      </p>
      <p class="muted">
        Plan: {status.plan === "supporter"
          ? "Supporter"
          : "Free"}{status.offline
          ? " · offline, showing the last known details"
          : ""}
      </p>
      {#if !status.consent.asked}
        <div class="consent" role="group" aria-labelledby="consent-title">
          <h4 id="consent-title">Before anything leaves this computer</h4>
          <p class="hint">
            Both are off. Turn one on only if you want it. You can change this
            any time here. <a
              href="https://github.com/Jacuzzik/hippocampus/blob/main/website/privacy.html"
              target="_blank"
              rel="noopener noreferrer">Privacy</a
            >
          </p>
          <Toggle
            bind:checked={sync}
            ariaLabel="Sync settings and briefings"
            label="Sync settings and briefings between your computers"
          />
          <Toggle
            bind:checked={usage}
            ariaLabel="Send usage reports"
            label="Send anonymous usage reports"
          />
          <button
            type="button"
            disabled={busy}
            onclick={() => run("user_consent", { sync, usage })}
            >Save choices</button
          >
        </div>
      {:else}
        <Toggle
          bind:checked={sync}
          ariaLabel="Sync settings and briefings"
          label="Sync settings and briefings"
          onchange={() => run("user_consent", { sync, usage })}
        />
        <Toggle
          bind:checked={usage}
          ariaLabel="Send usage reports"
          label="Send usage reports"
          onchange={() => run("user_consent", { sync, usage })}
        />
      {/if}
      <div class="row">
        <button
          type="button"
          disabled={busy}
          onclick={() => run("user_sign_out")}>Sign out</button
        >
        {#if confirmDelete}
          <button
            type="button"
            class="danger"
            disabled={busy}
            onclick={() => run("user_delete")}>Yes, delete my account</button
          >
          <button type="button" onclick={() => (confirmDelete = false)}
            >Keep it</button
          >
        {:else}
          <button type="button" onclick={() => (confirmDelete = true)}
            >Delete account</button
          >
        {/if}
      </div>
      {#if confirmDelete}
        <p class="hint" role="alert">
          This deletes the account on the service. Notes and agents on this
          computer are not touched.
        </p>
      {/if}
    {/if}
    {#if status.problem}<p class="error" role="alert">{status.problem}</p>{/if}
    {#if error}<p class="error" role="alert">{error}</p>{/if}
  </section>
{/if}

<style>
  .consent {
    display: grid;
    gap: var(--space-2);
    padding: var(--space-3);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
  }
  h4 {
    margin: 0;
  }
</style>
