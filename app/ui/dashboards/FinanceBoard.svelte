<script lang="ts">
  // The Money and spend dashboard: what AI costs each month. The user enters each plan (a monthly
  // subscription) and, for pay-as-you-go use, a price per million tokens; the token counts are the
  // real ones from each tool's logs. No price is guessed. Everything sits inside the board, so the
  // dashboard lock covers the form.
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import Button from "../controls/Button.svelte";
  import Dropdown from "../controls/Dropdown.svelte";
  import ErrorRow from "../controls/ErrorRow.svelte";
  import Loading from "../controls/Loading.svelte";
  import AnalyticPanel from "./AnalyticPanel.svelte";
  import { breakdown, dayLabels, short, type Panel } from "./model.ts";

  type Plan = {
    name: string;
    provider: string;
    monthly: number;
    per_million: number;
  };
  type Finance = {
    plans: { currency: string; plans: Plan[] };
    report: {
      currency: string;
      rows: (Plan & {
        provider_name: string;
        tokens: number;
        metered: number;
        total: number;
      })[];
      fixed: number;
      metered: number;
      total: number;
      projected: number;
      day: number;
      days_in_month: number;
      daily: number[];
    };
    providers: { id: string; name: string }[];
    currencies: string[];
  };

  let found = $state<Finance | null>(null);
  let error = $state<string | null>(null);
  let formError = $state<string | null>(null);
  let saved = $state("");
  let draft = $state<Plan[]>([]);
  let currency = $state("USD");

  async function read(): Promise<void> {
    error = null;
    try {
      found = await invoke<Finance>("sidecar_call", { method: "finance" });
      draft = found.plans.plans.map((plan) => ({ ...plan }));
      currency = found.plans.currency;
    } catch (cause) {
      error = String(cause);
    }
  }
  onMount(() => void read());

  async function save(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    formError = null;
    saved = "";
    try {
      found = await invoke<Finance>("sidecar_call", {
        method: "finance_save",
        params: {
          plans: {
            currency,
            plans: draft.map((plan) => ({
              ...plan,
              monthly: Number(plan.monthly) || 0,
              per_million: Number(plan.per_million) || 0,
            })),
          },
        },
      });
      draft = found.plans.plans.map((plan) => ({ ...plan }));
      saved = "Saved.";
    } catch (cause) {
      formError = String(cause);
    }
  }

  const money = (n: number): string =>
    new Intl.NumberFormat([], {
      style: "currency",
      currency: found?.report.currency ?? currency,
      maximumFractionDigits: 2,
    }).format(n);

  const providerOptions = $derived([
    { value: "", label: "No token count" },
    ...(found?.providers ?? []).map((p) => ({ value: p.id, label: p.name })),
  ]);

  const panels = $derived.by((): Panel[] => {
    if (!found) return [];
    const report = found.report;
    const days = report.daily.length;
    return [
      {
        kind: "breakdown",
        title: "This month by plan",
        note: `${money(report.total)} so far.`,
        rows: breakdown(
          report.rows.map((row) => [row.name, row.total] as [string, number]),
          money,
        ),
      },
      {
        kind: "trend",
        title: "Pay-as-you-go cost per day",
        note: `Last ${days} days, from your prices.`,
        labels: dayLabels(days),
        values: report.daily,
      },
      {
        kind: "list",
        title: "Each plan",
        note: "Plan price plus tokens times your price per million.",
        rows: report.rows.map((row) => ({
          title: row.name,
          badge: row.provider_name || "no token count",
          meta: money(row.total),
          lines: [
            `${money(row.monthly)} a month${row.per_million ? ` + ${short(row.tokens)} tokens at ${money(row.per_million)} per million = ${money(row.metered)}` : ""}`,
          ],
        })),
        empty: "No plan yet. Add what you pay below.",
      },
    ];
  });
</script>

{#if error}
  <ErrorRow message={error} onretry={read} />
{:else if found === null}
  <Loading what="your spend" />
{:else}
  {@const report = found.report}
  <ul class="tiles">
    <li>
      <span class="label">This month so far</span>
      <b>{money(report.total)}</b>
      <span class="note">Day {report.day} of {report.days_in_month}.</span>
    </li>
    <li>
      <span class="label">Expected for the month</span>
      <b>{money(report.projected)}</b>
      <span class="note">Plans, plus pay-as-you-go at this month's pace.</span>
    </li>
    <li>
      <span class="label">Plans</span>
      <b>{money(report.fixed)}</b>
      <span class="note">Fixed monthly prices.</span>
    </li>
    <li>
      <span class="label">Pay-as-you-go</span>
      <b>{money(report.metered)}</b>
      <span class="note">Real tokens times your price per million.</span>
    </li>
  </ul>

  <div class="panels">
    {#each panels as panel (panel.title)}
      <AnalyticPanel {panel} />
    {/each}
  </div>

  <form class="plans" onsubmit={save} aria-label="Your plans and prices">
    <div class="head">
      <h4>Your plans and prices</h4>
      <div class="currency">
        <span>Currency</span>
        <Dropdown
          label="Currency"
          options={found.currencies.map((c) => ({ value: c, label: c }))}
          bind:value={currency}
        />
      </div>
    </div>
    <p class="hint">
      Add each thing you pay for: a subscription's monthly price, and for a
      pay-as-you-go key, its price per million tokens and the tool whose tokens
      it pays for.
    </p>
    {#each draft as plan, i (i)}
      <div class="row">
        <label class="wide"
          >Name <input
            type="text"
            maxlength="60"
            placeholder="Claude Max"
            bind:value={plan.name}
          /></label
        >
        <div class="pick">
          <span>Tokens from</span>
          <Dropdown
            label={`Tokens from, plan ${i + 1}`}
            options={providerOptions}
            bind:value={plan.provider}
          />
        </div>
        <label
          >Monthly price <input
            type="number"
            min="0"
            step="0.01"
            placeholder="0"
            bind:value={plan.monthly}
          /></label
        >
        <label
          >Per million tokens <input
            type="number"
            min="0"
            step="0.01"
            placeholder="0"
            bind:value={plan.per_million}
          /></label
        >
        <Button
          size="sm"
          variant="ghost"
          aria-label={`Remove plan ${plan.name || i + 1}`}
          onclick={() => (draft = draft.filter((_, j) => j !== i))}
          >Remove</Button
        >
      </div>
    {/each}
    <div class="buttons">
      <Button
        onclick={() =>
          (draft = [
            ...draft,
            { name: "", provider: "", monthly: 0, per_million: 0 },
          ])}>Add a plan</Button
      >
      <Button type="submit" variant="primary">Save</Button>
      {#if saved}<span class="note" role="status">{saved}</span>{/if}
    </div>
    {#if formError}<p class="error" role="alert">{formError}</p>{/if}
  </form>
{/if}

<style>
  .tiles {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 200px), 1fr));
    gap: var(--space-3);
    margin: var(--space-3) 0 0;
    padding: 0;
    list-style: none;
  }

  .tiles li {
    display: grid;
    gap: var(--space-1);
    padding: var(--space-4);
    background:
      radial-gradient(
        120% 100% at 50% 100%,
        color-mix(in srgb, var(--color-accent) 16%, transparent),
        transparent 70%
      ),
      var(--tile-grid),
      var(--color-bg-1);
    border: 1px solid var(--color-border);
    border-top: 3px solid var(--color-accent);
    border-radius: var(--radius-md);
  }

  .tiles b {
    font-size: var(--font-size-xl);
    font-variant-numeric: tabular-nums;
  }

  .label,
  .note,
  .hint {
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
  }

  .panels {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 420px), 1fr));
    gap: var(--space-3);
    margin-top: var(--space-3);
  }

  .panels > :global(.panel) {
    padding: var(--space-4);
    background: var(--color-bg-1);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
  }

  .plans {
    display: grid;
    gap: var(--space-3);
    margin-top: var(--space-3);
    padding: var(--space-4);
    background: var(--pop-bg);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
  }

  .head {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-3);
    align-items: end;
    justify-content: space-between;
  }

  h4 {
    margin: 0;
    font-size: var(--font-size-md);
    font-weight: 500;
  }

  .hint {
    margin: 0;
  }

  .row {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: end;
  }

  .row label,
  .pick,
  .currency {
    display: flex;
    flex-direction: column;
    gap: var(--space-0);
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
  }

  .row .wide {
    flex: 1 1 var(--size-200);
  }

  .row input[type="number"] {
    width: var(--size-140);
  }

  .pick,
  .currency {
    width: var(--size-200);
  }

  .buttons {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: center;
  }

  .error {
    color: var(--color-danger);
  }
</style>
