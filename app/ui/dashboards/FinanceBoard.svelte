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
  import { breakdown, dayLabels, type Panel } from "./model.ts";

  type Plan = {
    name: string;
    provider: string;
    monthly: number;
    per_million: number;
  };
  type Sub = {
    name: string;
    store: "apple" | "google" | "other";
    price: number;
    period: "month" | "year" | "week";
    renews: string;
    status: "active" | "cancelled" | "expired";
    link: string;
  };
  type SubRow = Sub & {
    state: Sub["status"];
    active: boolean;
    monthly: number;
    manage: string;
    resubscribe: string;
  };
  type Wallet = {
    name: string;
    kind: "paypal" | "stripe" | "builtbybit" | "bank" | "crypto" | "other";
    balance: number;
    currency: string;
    updated: string;
    link: string;
  };
  type WalletRow = Wallet & { open: string };
  type Finance = {
    plans: {
      currency: string;
      plans: Plan[];
      subs: Sub[];
      wallets: Wallet[];
    };
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
      subs: SubRow[];
      subs_monthly: number;
      wallets: WalletRow[];
      wallet_totals: Record<string, number>;
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
  let subError = $state<string | null>(null);
  const blank = (): Sub => ({
    name: "",
    store: "apple",
    price: 0,
    period: "month",
    renews: "",
    status: "active",
    link: "",
  });
  let adding = $state<Sub>(blank());

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
            subs: found?.plans.subs ?? [],
            wallets: found?.plans.wallets ?? [],
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

  // Subscriptions are saved at once, with the plans as they are saved now.
  async function saveSubs(subs: Sub[]): Promise<void> {
    subError = null;
    if (!found) return;
    try {
      found = await invoke<Finance>("sidecar_call", {
        method: "finance_save",
        params: { plans: { ...found.plans, subs } },
      });
    } catch (cause) {
      subError = String(cause);
    }
  }

  const plain = (row: SubRow): Sub => ({
    name: row.name,
    store: row.store,
    price: row.price,
    period: row.period,
    renews: row.renews,
    status: row.status,
    link: row.link,
  });

  function setStatus(row: SubRow, status: Sub["status"]): void {
    if (!found) return;
    void saveSubs(
      found.report.subs.map((s) =>
        s === row ? { ...plain(s), status } : plain(s),
      ),
    );
  }

  function removeSub(row: SubRow): void {
    if (!found) return;
    void saveSubs(found.report.subs.filter((s) => s !== row).map(plain));
  }

  function addSub(event: SubmitEvent): void {
    event.preventDefault();
    if (!found || !adding.name.trim()) return;
    void saveSubs([
      ...found.report.subs.map(plain),
      { ...adding, price: Number(adding.price) || 0 },
    ]).then(() => {
      if (!subError) adding = blank();
    });
  }

  // Wallets are saved at once too, the same way.
  const today = (): string => new Date().toISOString().slice(0, 10);
  const blankWallet = (): Wallet => ({
    name: "",
    kind: "paypal",
    balance: 0,
    currency: found?.plans.currency ?? "USD",
    updated: today(),
    link: "",
  });
  let wallet = $state<Wallet>(blankWallet());
  let walletError = $state<string | null>(null);
  const plainWallet = (row: WalletRow): Wallet => ({
    name: row.name,
    kind: row.kind,
    balance: row.balance,
    currency: row.currency,
    updated: row.updated,
    link: row.link,
  });

  async function saveWallets(wallets: Wallet[]): Promise<boolean> {
    walletError = null;
    if (!found) return false;
    try {
      found = await invoke<Finance>("sidecar_call", {
        method: "finance_save",
        params: { plans: { ...found.plans, wallets } },
      });
      return true;
    } catch (cause) {
      walletError = String(cause);
      return false;
    }
  }

  function addWallet(event: SubmitEvent): void {
    event.preventDefault();
    if (!found || !wallet.name.trim()) return;
    void saveWallets([
      ...found.report.wallets.map(plainWallet),
      { ...wallet, balance: Number(wallet.balance) || 0 },
    ]).then((ok) => {
      if (ok) wallet = blankWallet();
    });
  }

  function setBalance(row: WalletRow, value: string): void {
    if (!found) return;
    const balance = Number(value);
    if (!Number.isFinite(balance) || balance < 0) return;
    void saveWallets(
      found.report.wallets.map((w) =>
        w === row
          ? { ...plainWallet(w), balance, updated: today() }
          : plainWallet(w),
      ),
    );
  }

  function removeWallet(row: WalletRow): void {
    if (!found) return;
    void saveWallets(
      found.report.wallets.filter((w) => w !== row).map(plainWallet),
    );
  }

  const KIND: Record<Wallet["kind"], string> = {
    paypal: "PayPal",
    stripe: "Stripe",
    builtbybit: "BuiltByBit",
    bank: "Bank",
    crypto: "Crypto wallet",
    other: "Other",
  };

  const inCurrency = (n: number, code: string): string =>
    new Intl.NumberFormat([], {
      style: "currency",
      currency: code,
      maximumFractionDigits: 2,
    }).format(n);

  async function openLink(url: string): Promise<void> {
    subError = null;
    try {
      await invoke("sidecar_call", { method: "open_link", params: { url } });
    } catch (cause) {
      subError = String(cause);
    }
  }

  const STORE: Record<Sub["store"], string> = {
    apple: "Apple",
    google: "Google Play",
    other: "Other",
  };
  const PER: Record<Sub["period"], string> = {
    month: "a month",
    year: "a year",
    week: "a week",
  };

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

  // The numbers and charts first; each form on its own tab, so the board fits the window.
  const TABS = [
    { id: "overview", label: "Overview" },
    { id: "plans", label: "Plans and prices" },
    { id: "subs", label: "Subscriptions" },
    { id: "wallets", label: "Wallets" },
  ] as const;
  let tab = $state<(typeof TABS)[number]["id"]>("overview");

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
    ];
  });
</script>

{#if error}
  <ErrorRow message={error} onretry={read} />
{:else if found === null}
  <Loading what="your spend" />
{:else}
  {@const report = found.report}
  {@const live = report.subs.filter((s) => s.active)}
  {@const gone = report.subs.filter((s) => !s.active)}
  <div class="tabs" role="tablist" aria-label="Money">
    {#each TABS as item (item.id)}
      <button
        type="button"
        role="tab"
        aria-selected={tab === item.id}
        class:on={tab === item.id}
        onclick={() => (tab = item.id)}>{item.label}</button
      >
    {/each}
  </div>
  {#if tab === "overview"}
    <ul class="tiles">
      <li>
        <span class="label">This month so far</span>
        <b>{money(report.total)}</b>
        <span class="note">Day {report.day} of {report.days_in_month}.</span>
      </li>
      <li>
        <span class="label">Expected for the month</span>
        <b>{money(report.projected)}</b>
        <span class="note">Plans, plus pay-as-you-go at this month's pace.</span
        >
      </li>
      <li>
        <span class="label">Plans</span>
        <b>{money(report.fixed)}</b>
        <span class="note">Fixed monthly prices.</span>
      </li>
      <li>
        <span class="label">Subscriptions</span>
        <b>{money(report.subs_monthly)}</b>
        <span class="note"
          >{report.subs.filter((s) => s.active).length} active, as a monthly amount.</span
        >
      </li>
      <li>
        <span class="label">Wallets</span>
        <b
          >{Object.entries(report.wallet_totals)
            .map(([code, n]) => inCurrency(n, code))
            .join(" + ") || money(0)}</b
        >
        <span class="note"
          >{report.wallets.length} wallet{report.wallets.length === 1
            ? ""
            : "s"}, as you last entered them.</span
        >
      </li>
      <li>
        <span class="label">Pay-as-you-go</span>
        <b>{money(report.metered)}</b>
        <span class="note">Real tokens times your price per million.</span>
      </li>
    </ul>

    <div class="panels">
      {#each panels as panel (panel.title)}
        <AnalyticPanel {panel} fill />
      {/each}
    </div>
  {:else if tab === "subs"}
    <div class="pane">
      <section class="plans subs" aria-label="Subscriptions">
        <div class="head">
          <h4>Subscriptions</h4>
          <div class="buttons">
            <Button
              size="sm"
              onclick={() =>
                openLink("https://apps.apple.com/account/subscriptions")}
              >Open Apple subscriptions</Button
            >
          </div>
        </div>
        <p class="hint">
          Apple does not let other apps read your subscriptions, so add each one
          here. Cancel and Resubscribe open Apple's own subscriptions page,
          where you sign in and make the change; then mark it here.
        </p>
        {#if subError}<p class="error" role="alert">{subError}</p>{/if}
        <ul class="sublist" aria-label="Active subscriptions">
          {#each live as row, i (`${i}:${row.name}`)}
            <li>
              <span class="subname"
                ><b>{row.name}</b>
                <span class="note"
                  >{STORE[row.store]} · {money(row.price)}
                  {PER[row.period]}{row.renews
                    ? ` · renews ${row.renews}`
                    : ""}</span
                ></span
              >
              <span class="buttons">
                {#if row.manage || row.link}
                  <Button
                    size="sm"
                    onclick={() => openLink(row.link || row.manage)}
                    >Cancel on {STORE[row.store]}</Button
                  >
                {/if}
                <Button size="sm" onclick={() => setStatus(row, "cancelled")}
                  >Mark cancelled</Button
                >
                <Button
                  size="sm"
                  variant="ghost"
                  aria-label={`Remove ${row.name}`}
                  onclick={() => removeSub(row)}>Remove</Button
                >
              </span>
            </li>
          {:else}
            <li class="note">No active subscription added yet.</li>
          {/each}
        </ul>
        <form class="row" onsubmit={addSub} aria-label="Add a subscription">
          <label class="wide"
            >Name <input
              type="text"
              maxlength="60"
              placeholder="iCloud+"
              bind:value={adding.name}
            /></label
          >
          <div class="pick">
            <span>Store</span>
            <Dropdown
              label="Store"
              options={[
                { value: "apple", label: "Apple" },
                { value: "google", label: "Google Play" },
                { value: "other", label: "Other" },
              ]}
              bind:value={adding.store}
            />
          </div>
          <label
            >Price <input
              type="number"
              min="0"
              step="0.01"
              bind:value={adding.price}
            /></label
          >
          <div class="pick">
            <span>Every</span>
            <Dropdown
              label="Billing period"
              options={[
                { value: "month", label: "Month" },
                { value: "year", label: "Year" },
                { value: "week", label: "Week" },
              ]}
              bind:value={adding.period}
            />
          </div>
          <label>Renews <input type="date" bind:value={adding.renews} /></label>
          <label class="wide"
            >Renew link (optional) <input
              type="url"
              placeholder="https://…"
              bind:value={adding.link}
            /></label
          >
          <Button type="submit" variant="primary" disabled={!adding.name.trim()}
            >Add subscription</Button
          >
        </form>
      </section>
      {@render inactiveList(gone)}
    </div>
  {:else if tab === "wallets"}
    <div class="pane">
      <section class="plans wallets" aria-label="Wallets">
        <div class="head"><h4>Wallets</h4></div>
        <p class="hint">
          The money you hold with PayPal, Stripe, a bank or a crypto wallet.
          These services have no way for an app to read a wallet balance, so
          enter it here and update it when it changes. Open goes to the
          service's own wallet page.
        </p>
        {#if walletError}<p class="error" role="alert">{walletError}</p>{/if}
        <ul class="sublist" aria-label="Your wallets">
          {#each report.wallets as row, i (`${i}:${row.name}`)}
            <li>
              <span class="subname"
                ><b>{row.name}</b>
                <span class="note"
                  >{KIND[row.kind]} · {inCurrency(
                    row.balance,
                    row.currency,
                  )}{row.updated ? ` · as of ${row.updated}` : ""}</span
                ></span
              >
              <span class="buttons">
                <input
                  class="balance"
                  type="number"
                  min="0"
                  step="0.01"
                  value={row.balance}
                  aria-label={`Balance of ${row.name}`}
                  onchange={(e) => setBalance(row, e.currentTarget.value)}
                />
                {#if row.open}
                  <Button size="sm" onclick={() => openLink(row.open)}
                    >Open {KIND[row.kind]}</Button
                  >
                {/if}
                <Button
                  size="sm"
                  variant="ghost"
                  aria-label={`Remove ${row.name}`}
                  onclick={() => removeWallet(row)}>Remove</Button
                >
              </span>
            </li>
          {:else}
            <li class="note">No wallet added yet.</li>
          {/each}
        </ul>
        <form class="row" onsubmit={addWallet} aria-label="Add a wallet">
          <label class="wide"
            >Wallet name <input
              type="text"
              maxlength="60"
              placeholder="PayPal business"
              bind:value={wallet.name}
            /></label
          >
          <div class="pick">
            <span>Service</span>
            <Dropdown
              label="Wallet service"
              options={Object.entries(KIND).map(([value, label]) => ({
                value,
                label,
              }))}
              bind:value={wallet.kind}
            />
          </div>
          <label
            >Balance <input
              type="number"
              min="0"
              step="0.01"
              bind:value={wallet.balance}
            /></label
          >
          <div class="pick">
            <span>Currency</span>
            <Dropdown
              label="Wallet currency"
              options={found.currencies.map((c) => ({ value: c, label: c }))}
              bind:value={wallet.currency}
            />
          </div>
          <label class="wide"
            >Wallet link (optional) <input
              type="url"
              placeholder="https://…"
              bind:value={wallet.link}
            /></label
          >
          <Button type="submit" variant="primary" disabled={!wallet.name.trim()}
            >Add wallet</Button
          >
        </form>
      </section>
    </div>
  {:else}
    <div class="pane">
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
          pay-as-you-go key, its price per million tokens and the tool whose
          tokens it pays for.
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
    </div>
  {/if}
{/if}

{#snippet inactiveList(gone: SubRow[])}
  <section class="plans inactive" aria-label="Inactive subscriptions">
    <h4>Inactive subscriptions</h4>
    <ul class="sublist">
      {#each gone as row, i (`${i}:${row.name}`)}
        <li>
          <span class="subname"
            ><b>{row.name}</b>
            <span class="note"
              >{row.state === "expired" ? "Expired" : "Cancelled"} · {STORE[
                row.store
              ]} · {money(row.price)}
              {PER[row.period]}{row.renews
                ? ` · ${row.state === "expired" ? "ended" : "ends"} ${row.renews}`
                : ""}</span
            ></span
          >
          <span class="buttons">
            {#if row.resubscribe}
              <Button
                size="sm"
                variant="primary"
                onclick={() => openLink(row.resubscribe)}>Resubscribe</Button
              >
            {/if}
            <Button size="sm" onclick={() => setStatus(row, "active")}
              >Mark active</Button
            >
            <Button
              size="sm"
              variant="ghost"
              aria-label={`Remove ${row.name}`}
              onclick={() => removeSub(row)}>Remove</Button
            >
          </span>
        </li>
      {:else}
        <li class="note">No cancelled or expired subscription.</li>
      {/each}
    </ul>
  </section>
{/snippet}

<style>
  .tabs {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-1);
    margin-top: var(--space-2);
  }

  .tabs button {
    min-height: var(--size-28);
    padding: var(--space-1) var(--space-3);
    color: var(--color-text-muted);
    font: inherit;
    background: transparent;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
    cursor: pointer;
  }

  .tabs button.on {
    color: var(--color-accent);
    background: color-mix(in srgb, var(--color-accent) 14%, transparent);
    border-color: color-mix(in srgb, var(--color-accent) 45%, transparent);
  }

  /* A form tab: the forms scroll inside the board, never the page. */
  .pane {
    flex: 1 1 0;
    min-height: 0;
    overflow-y: auto;
  }

  .tiles {
    flex: 0 0 auto;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(min(100%, 140px), 1fr));
    gap: var(--space-3);
    margin: var(--space-3) 0 0;
    padding: 0;
    list-style: none;
  }

  .tiles li {
    display: grid;
    gap: var(--space-1);
    align-content: start;
    padding: var(--space-3) var(--space-4);
    background:
      radial-gradient(
        120% 100% at 50% 100%,
        color-mix(in srgb, var(--color-accent) 16%, transparent),
        transparent 70%
      ),
      var(--tile-grid), var(--color-bg-1);
    border: 1px solid var(--color-border);
    border-top: 3px solid var(--color-accent);
    border-radius: var(--radius-md);
  }

  .tiles b {
    font-size: var(--font-size-xl);
    font-variant-numeric: tabular-nums;
  }

  /* Two lines at most, so the six numbers stay one short row. */
  .tiles .note {
    display: -webkit-box;
    -webkit-box-orient: vertical;
    -webkit-line-clamp: 2;
    line-clamp: 2;
    overflow: hidden;
    font-size: var(--font-size-xs);
  }

  .label,
  .note,
  .hint {
    color: var(--color-text-muted);
    font-size: var(--font-size-sm);
  }

  /* The two charts share the height left under the numbers. */
  .panels {
    flex: 1 1 0;
    min-height: 0;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    grid-auto-rows: minmax(0, 1fr);
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

  .sublist {
    display: grid;
    gap: var(--space-2);
    margin: 0;
    padding: 0;
    list-style: none;
  }

  .sublist li {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: center;
    justify-content: space-between;
    padding: var(--space-2) var(--space-3);
    background: var(--color-bg-1);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
  }

  .subname {
    display: grid;
    gap: var(--space-0);
    min-width: 0;
  }

  .balance {
    width: 7.5rem;
  }

  .inactive .sublist li:not(.note) {
    opacity: 0.75;
  }
</style>
