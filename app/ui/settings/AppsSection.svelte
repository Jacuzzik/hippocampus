<script lang="ts">
  // Connected apps: the catalogue, with a form to connect each one. A key goes to the system keychain
  // through the backend; it is never shown again, only its last four characters.
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import Button from "../controls/Button.svelte";
  import ErrorRow from "../controls/ErrorRow.svelte";
  import Loading from "../controls/Loading.svelte";

  type AppRow = {
    id: string;
    name: string;
    what: string;
    key_help: string;
    fields: { key: string; label: string; example: string }[];
    saved: Record<string, string>;
    connected: boolean;
    hint: string | null;
    numbers: string[];
  };
  let rows = $state<AppRow[] | null>(null);
  let error = $state<string | null>(null);
  let open = $state<string | null>(null);
  let key = $state("");
  let fields = $state<Record<string, string>>({});
  let formError = $state<string | null>(null);
  let busy = $state(false);
  let filter = $state("");

  async function load(): Promise<void> {
    error = null;
    try {
      rows = (
        await invoke<{ apps: AppRow[] }>("sidecar_call", { method: "apps" })
      ).apps;
    } catch (cause) {
      error = String(cause);
    }
  }
  onMount(() => void load());

  function start(row: AppRow): void {
    open = row.id;
    key = "";
    fields = { ...row.saved };
    formError = null;
  }

  async function send(
    method: string,
    params: Record<string, unknown>,
  ): Promise<void> {
    formError = null;
    busy = true;
    try {
      rows = (
        await invoke<{ apps: AppRow[] }>("sidecar_call", { method, params })
      ).apps;
      open = null;
      key = "";
      // The dashboards list its connected apps; tell it the list changed.
      window.dispatchEvent(new CustomEvent("apps-changed"));
    } catch (cause) {
      formError = String(cause);
    } finally {
      busy = false;
    }
  }

  const shown = $derived(
    (rows ?? []).filter((row) =>
      `${row.name} ${row.what}`
        .toLowerCase()
        .includes(filter.trim().toLowerCase()),
    ),
  );
  const connected = $derived(
    (rows ?? []).filter((row) => row.connected).length,
  );
</script>

<section class="control-section">
  <h3>Connected apps</h3>
  <p class="muted">
    Connect an app with your own key and it gets a dashboard of its numbers.
    Keys are kept in the system keychain. Requests only read; nothing is changed
    in the app.
  </p>
  {#if error}
    <ErrorRow message={error} onretry={load} />
  {:else if rows === null}
    <Loading what="apps" />
  {:else}
    <div class="top">
      <input
        type="search"
        aria-label="Find an app"
        placeholder="Find an app"
        bind:value={filter}
      />
      <span class="muted" role="status"
        >{connected} of {rows.length} connected</span
      >
    </div>
    <ul class="apps">
      {#each shown as row (row.id)}
        <li>
          <div class="line">
            <span class="name">
              <b>{row.name}</b>
              <span class="muted">{row.what}</span>
            </span>
            <span class="state" class:on={row.connected}
              >{row.connected
                ? `Connected${row.hint ? ` · key ends ${row.hint}` : ""}`
                : "Not connected"}</span
            >
            {#if row.connected}
              <Button
                aria-label={`Disconnect ${row.name}`}
                disabled={busy}
                onclick={() => send("app_disconnect", { id: row.id })}
                >Disconnect</Button
              >
            {:else if open !== row.id}
              <Button
                aria-label={`Connect ${row.name}`}
                onclick={() => start(row)}>Connect</Button
              >
            {/if}
          </div>
          {#if open === row.id}
            <form
              class="connect"
              onsubmit={(e) => {
                e.preventDefault();
                void send("app_connect", { id: row.id, key, fields });
              }}
            >
              {#each row.fields as field (field.key)}
                <label
                  >{field.label}
                  <input
                    type="text"
                    placeholder={field.example}
                    bind:value={fields[field.key]}
                  /></label
                >
              {/each}
              <label
                >Key for {row.name}
                <input
                  type="password"
                  autocomplete="off"
                  bind:value={key}
                /></label
              >
              <p class="muted">
                {row.key_help} It shows: {row.numbers.join(", ")}.
              </p>
              {#if formError}<p class="error" role="alert">{formError}</p>{/if}
              <div class="buttons">
                <Button onclick={() => (open = null)}>Cancel</Button>
                <Button
                  type="submit"
                  variant="primary"
                  disabled={busy || !key.trim()}>Save key</Button
                >
              </div>
            </form>
          {/if}
        </li>
      {/each}
    </ul>
    {#if shown.length === 0}<p class="muted">No app matches "{filter}".</p>{/if}
  {/if}
</section>

<style>
  .top {
    display: flex;
    gap: var(--space-3);
    align-items: center;
    margin: var(--space-2) 0;
  }

  .apps {
    display: grid;
    gap: var(--space-2);
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .apps li {
    padding: var(--space-2) var(--space-3);
    background: var(--color-bg-1);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
  }

  .line {
    display: flex;
    gap: var(--space-3);
    align-items: center;
  }

  .name {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-width: 0;
  }

  .state {
    color: var(--color-text-muted);
    white-space: nowrap;
  }

  .state.on {
    color: var(--color-text);
  }

  .connect {
    display: grid;
    gap: var(--space-2);
    margin-top: var(--space-2);
  }

  .connect label {
    display: grid;
    gap: var(--space-0);
    color: var(--color-text-muted);
  }

  .buttons {
    display: flex;
    gap: var(--space-2);
    justify-content: flex-end;
  }

  input {
    min-height: var(--size-28);
    padding: var(--space-1) var(--space-2);
    color: var(--color-text);
    font: inherit;
    background: var(--color-surface);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
  }

  .muted {
    color: var(--color-text-muted);
  }

  .error {
    color: var(--color-danger);
  }
</style>
