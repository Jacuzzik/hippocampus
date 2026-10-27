<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import { WINDOWS, overrunOf, parseCap, usageLine, type Caps } from "./model";

  // Token caps per day, week and month. 0 means no cap. Over a cap, the assistant pauses.
  type Scope = { caps: Caps; used: Caps };
  type BudgetState = {
    caps: { app: Caps; assistant: Caps };
    used: { app: Caps; assistant: Caps };
    allowance: boolean;
  };
  const LABELS = { app: "Whole app", assistant: "Assistant" } as const;
  const SCOPES = ["app", "assistant"] as const;

  let budget = $state<BudgetState | null>(null);
  let draft = $state<Record<string, string>>({});
  let error = $state<string | null>(null);
  let saved = $state(false);

  async function load(): Promise<void> {
    try {
      budget = await invoke<BudgetState>("sidecar_call", { method: "budget" });
      draft = Object.fromEntries(
        Object.entries(budget.caps).flatMap(([scope, caps]) =>
          WINDOWS.map((w) => [`${scope}.${w}`, caps[w] ? String(caps[w]) : ""]),
        ),
      );
    } catch (cause) {
      error = String(cause);
    }
  }

  function scopeOf(key: "app" | "assistant"): Scope | null {
    return budget ? { caps: budget.caps[key], used: budget.used[key] } : null;
  }

  async function save(): Promise<void> {
    error = null;
    saved = false;
    const body: Record<string, Caps> = {};
    for (const scope of ["app", "assistant"] as const) {
      const caps = {} as Caps;
      for (const w of WINDOWS) {
        const value = parseCap(draft[`${scope}.${w}`] ?? "");
        if (value === null) {
          error = "A cap is a whole number, or empty for no cap.";
          return;
        }
        caps[w] = value;
      }
      body[scope] = caps;
    }
    try {
      budget = await invoke<BudgetState>("sidecar_call", {
        method: "set_budget",
        params: body,
      });
      saved = true;
    } catch (cause) {
      error = String(cause);
    }
  }

  async function allowOne(): Promise<void> {
    try {
      await invoke("sidecar_call", { method: "budget_allow" });
      await load();
    } catch (cause) {
      error = String(cause);
    }
  }

  // The first cap reached, for the status line. The assistant also shows a card when it pauses.
  const reached = $derived.by(() => {
    for (const key of ["app", "assistant"] as const) {
      const scope = scopeOf(key);
      const hit = scope && overrunOf(key, scope.caps, scope.used);
      if (hit) return hit;
    }
    return null;
  });

  onMount(() => void load());
</script>

<section class="control-section" aria-labelledby="control-budget">
  <h3 id="control-budget">Token budget</h3>
  <p class="hint">
    A cap on model tokens per day, week and month. Over a cap the assistant
    pauses and waits for you. 0 or empty means no cap.
  </p>
  {#if reached}
    <p class="error" role="status">
      Paused: the {LABELS[reached.scope as "app" | "assistant"].toLowerCase()}
      {reached.window} cap is used ({usageLine(reached.used, reached.cap)}).
    </p>
  {/if}
  {#if budget}
    {#each SCOPES as key (key)}
      <div class="budget-scope">
        <p class="muted">
          {LABELS[key]}: today {usageLine(
            budget.used[key].daily,
            budget.caps[key].daily,
          )}
        </p>
        <div class="row">
          {#each WINDOWS as w (w)}
            <label>
              {w}
              <input
                type="text"
                inputmode="numeric"
                size="8"
                aria-label={`${LABELS[key]} ${w} cap`}
                bind:value={draft[`${key}.${w}`]}
              />
            </label>
          {/each}
        </div>
      </div>
    {/each}
    <div class="row">
      <button type="button" class="primary" onclick={save}>Save caps</button>
      <button
        type="button"
        disabled={!budget.allowance && !reached}
        onclick={allowOne}>Allow one more request</button
      >
      {#if saved}<span class="muted">Saved.</span>{/if}
    </div>
  {/if}
  {#if error}<p class="error" role="alert">{error}</p>{/if}
</section>
