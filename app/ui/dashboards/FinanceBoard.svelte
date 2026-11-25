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
  // Rows found in receipts and added files carry `auto`; they are shown, never saved unless kept.
  type Found_ = { auto?: boolean; currency?: string; store_name?: string };
  type Sub = {
    name: string;
    store: "apple" | "google" | "other";
    price: number;
    period: "month" | "year" | "week";
    renews: string;
    status: "active" | "cancelled" | "expired";
    link: string;
  };
  type SubRow = Sub &
    Found_ & {
      state: Sub["status"];
      active: boolean;
      monthly: number;
      manage: string;
      resubscribe: string;
    };
  type Wallet = {
    name: string;
    kind:
      | "paypal"
      | "stripe"
      | "builtbybit"
      | "shopify"
      | "bank"
      | "crypto"
      | "other";
    balance: number;
    currency: string;
    updated: string;
    link: string;
  };
  type WalletRow = Wallet & {
    open: string;
    auto: boolean;
    received_month: number;
    received_year: number;
    spent_month: number;
    last: string;
    moves: number;
    pays_for: string[];
    pays_monthly: number;
    covers_months: number | null;
  };
  type Finance = {
    plans: {
      currency: string;
      plans: Plan[];
      subs: Sub[];
      wallets: Wallet[];
      hidden?: string[];
    };
    report: {
      currency: string;
      history: { month: string; spent: number; received: number }[];
      found: number;
      rows: (Plan &
        Found_ & {
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
  onMount(() => {
    void read();
    void readMail();
  });

  // Subscriptions and purchases found by the app: receipts in the user's Gmail, plus files the
  // user downloads (Google Takeout's Play part, Apple's data copy, a bank statement as CSV).
  type Found = {
    date: string;
    store: string;
    store_name?: string;
    item: string;
    amount: number | null;
    currency: string;
    source?: string;
  };
  type FoundSub = {
    name: string;
    store: string;
    store_name?: string;
    price: number | null;
    currency: string;
    period: "month" | "year" | "week";
    status: "active" | "cancelled" | "inactive";
    last: string;
    renews: string;
    charges: number;
    how: "notice" | "repeated charges";
    sources: string[];
    evidence: { date: string; subject: string }[];
  };
  type Mail = {
    connected: boolean;
    account: string;
    network: string;
    scanned_at: string;
    read: number;
    messages: number;
    files: { name: string; added: string; events: number }[];
    found: {
      subscriptions: FoundSub[];
      purchases: Found[];
      sales: Found[];
      refunds: Found[];
    } | null;
  };
  const STORES: Record<string, string> = {
    apple: "Apple",
    google: "Google Play",
    paypal: "PayPal",
    stripe: "Stripe",
    shopify: "Shopify",
    builtbybit: "BuiltByBit",
    steam: "Steam",
    amazon: "Amazon",
  };
  const storeName = (row: { store: string; store_name?: string }): string =>
    row.store_name || STORES[row.store] || row.store;
  let mail = $state<Mail | null>(null);
  let mailBusy = $state(false);
  let mailError = $state("");
  let mailNote = $state("");
  let mailForm = $state({ email: "", password: "" });
  let showSources = $state(false);
  let picker = $state<HTMLInputElement | null>(null);

  async function mailCall(method: string, params?: object): Promise<void> {
    mailBusy = true;
    mailError = "";
    mailNote = "";
    try {
      mail = await invoke<Mail>("sidecar_call", { method, params });
      // What was found fills the plans, subscriptions, wallets and overview.
      if (method !== "mail_status") void read();
    } catch (cause) {
      mailError = String(cause);
    } finally {
      mailBusy = false;
    }
  }
  const readMail = () => mailCall("mail_status");
  async function connectMail(event: SubmitEvent): Promise<void> {
    event.preventDefault();
    await mailCall("mail_connect", { ...mailForm });
    if (!mailError) {
      mailForm = { email: "", password: "" };
      showSources = false;
    }
  }
  // A downloaded file goes to the backend as base64; it reads the purchases and keeps only those.
  async function addFile(event: Event): Promise<void> {
    const input = event.currentTarget as HTMLInputElement;
    const file = input.files?.[0];
    input.value = "";
    if (!file) return;
    if (file.size > 30_000_000) {
      mailError =
        "The file is larger than 30 MB. Pick only the Google Play part, or one statement.";
      return;
    }
    const bytes = new Uint8Array(await file.arrayBuffer());
    let binary = "";
    for (let i = 0; i < bytes.length; i += 0x8000)
      binary += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
    await mailCall("purchases_import", { name: file.name, data: btoa(binary) });
    if (!mailError) {
      mailNote = `Read ${file.name}.`;
      showSources = false;
    }
  }

  const priced = (amount: number | null, code: string): string =>
    amount === null ? "" : code ? inCurrency(amount, code) : money(amount);
  const foundRow = (row: Found) => ({
    title: row.item,
    badge: storeName(row),
    meta: [priced(row.amount, row.currency), row.date]
      .filter(Boolean)
      .join(" · "),
  });
  const mailPanels = $derived.by((): Panel[] => {
    const f = mail?.found;
    if (!f) return [];
    return [
      {
        kind: "list",
        title: "Subscriptions found",
        note: `${f.subscriptions.filter((s) => s.status === "active").length} active of ${f.subscriptions.length}`,
        rows: f.subscriptions.map((s) => ({
          title: s.name,
          badge: `${storeName(s)} · ${s.status}`,
          meta:
            s.price === null
              ? ""
              : `${priced(s.price, s.currency)} ${PER[s.period]}`,
          lines: [
            [
              s.renews
                ? `${s.status === "active" ? "Renews" : "Ends"} ${s.renews}`
                : s.last
                  ? `Last charged ${s.last}`
                  : "",
              s.how === "repeated charges"
                ? `charged ${s.charges} times`
                : s.charges
                  ? `${s.charges} receipt${s.charges === 1 ? "" : "s"}`
                  : "",
              s.sources.includes("file") ? "from a file" : "",
            ]
              .filter(Boolean)
              .join(" · "),
            s.evidence[0]?.subject ? `“${s.evidence[0].subject}”` : "",
          ].filter(Boolean),
          tone:
            s.status === "active"
              ? ("good" as const)
              : s.status === "cancelled"
                ? ("warn" as const)
                : ("plain" as const),
        })),
        empty: "No subscription found yet.",
      },
      {
        kind: "list",
        title: "Latest purchases",
        note: `${f.purchases.length} found`,
        rows: f.purchases.map(foundRow),
        empty: "No purchase receipt found.",
      },
      {
        kind: "list",
        title: "Latest sales",
        note: "Money you received: PayPal, Shopify, BuiltByBit, Stripe.",
        rows: f.sales.map((row) => ({
          ...foundRow(row),
          tone: "good" as const,
        })),
        empty: "No sale found.",
      },
      {
        kind: "list",
        title: "Refunds",
        note: `${f.refunds.length} found`,
        rows: f.refunds.map(foundRow),
        empty: "No refund found.",
      },
    ];
  });

  // The found subscriptions go into the user's own list (the ones not there yet), where the
  // Overview counts them and Cancel and Resubscribe work.
  function keepFound(): void {
    const f = mail?.found;
    if (!found || !f) return;
    const have = new Set(own().map((s) => s.name.toLowerCase()));
    const fresh = f.subscriptions
      .filter((s) => !have.has(s.name.toLowerCase()))
      .map((s): Sub => ({
        name: s.name.slice(0, 60),
        store: s.store === "apple" || s.store === "google" ? s.store : "other",
        price: s.price ?? 0,
        period: s.period,
        renews: s.renews,
        status:
          s.status === "active"
            ? "active"
            : s.status === "cancelled"
              ? "cancelled"
              : "expired",
        link: "",
      }));
    void saveSubs([...own().map(plain), ...fresh]).then(() => {
      if (!subError)
        mailNote = fresh.length
          ? `Added ${fresh.length} to your subscriptions.`
          : "They are all in your subscriptions already.";
    });
  }

  function keepPlan(row: Plan): void {
    draft = [
      ...draft,
      {
        name: row.name,
        provider: row.provider,
        monthly: row.monthly,
        per_million: 0,
      },
    ];
    void save();
  }

  async function save(event?: SubmitEvent): Promise<void> {
    event?.preventDefault();
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

  const own = (): SubRow[] => found?.report.subs.filter((s) => !s.auto) ?? [];
  // Hiding a found row keeps it off the board; it comes back if the user unhides it in the file.
  async function hide(name: string): Promise<void> {
    if (!found) return;
    try {
      found = await invoke<Finance>("sidecar_call", {
        method: "finance_save",
        params: {
          plans: {
            ...found.plans,
            hidden: [...(found.plans.hidden ?? []), name],
          },
        },
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
    // A found row the user acts on becomes one of theirs.
    void saveSubs([
      ...own()
        .filter((s) => s !== row)
        .map(plain),
      { ...plain(row), status },
    ]);
  }

  function removeSub(row: SubRow): void {
    if (!found) return;
    if (row.auto) {
      void hide(row.name);
      return;
    }
    void saveSubs(
      own()
        .filter((s) => s !== row)
        .map(plain),
    );
  }

  function addSub(event: SubmitEvent): void {
    event.preventDefault();
    if (!found || !adding.name.trim()) return;
    void saveSubs([
      ...own().map(plain),
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

  const ownWallets = (): WalletRow[] =>
    found?.report.wallets.filter((w) => !w.auto) ?? [];
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
      ...ownWallets().map(plainWallet),
      { ...wallet, balance: Number(wallet.balance) || 0 },
    ]).then((ok) => {
      if (ok) wallet = blankWallet();
    });
  }

  function setBalance(row: WalletRow, value: string): void {
    if (!found) return;
    const balance = Number(value);
    if (!Number.isFinite(balance) || balance < 0) return;
    void saveWallets([
      ...ownWallets()
        .filter((w) => w !== row)
        .map(plainWallet),
      { ...plainWallet(row), balance, updated: today() },
    ]);
  }

  function removeWallet(row: WalletRow): void {
    if (!found) return;
    if (row.auto) {
      void hide(`wallet:${row.name}`);
      return;
    }
    void saveWallets(
      ownWallets()
        .filter((w) => w !== row)
        .map(plainWallet),
    );
  }

  const KIND: Record<Wallet["kind"], string> = {
    paypal: "PayPal",
    stripe: "Stripe",
    builtbybit: "BuiltByBit",
    shopify: "Shopify",
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
    { id: "mail", label: "Find subscriptions" },
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
      ...(report.found
        ? [
            {
              kind: "trend" as const,
              title: "Spent per month, from receipts",
              note: `Last 12 months. Received: ${money(
                report.history.reduce((n, m) => n + m.received, 0),
              )}.`,
              labels: report.history.map((m) => m.month.slice(2)),
              values: report.history.map((m) => m.spent),
            },
          ]
        : []),
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
            : "s"} · {money(
            report.wallets
              .filter((w) => w.currency === report.currency)
              .reduce((n, w) => n + w.received_month, 0),
          )} came in this month.</span
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
  {:else if tab === "mail"}
    <input
      bind:this={picker}
      type="file"
      accept=".zip,.json,.csv"
      hidden
      aria-label="Add a file"
      onchange={addFile}
    />
    {#if mail?.found}
      <div class="mailbar">
        {#if mail.connected}
          <span class="note"
            >Gmail <b>{mail.account}</b> · {mail.messages} receipts in {mail.read}
            emails · scanned {mail.scanned_at
              .slice(0, 16)
              .replace("T", " ")}</span
          >
          <Button
            size="sm"
            disabled={mailBusy}
            onclick={() => mailCall("mail_scan")}
            >{mailBusy ? "Scanning…" : "Scan again"}</Button
          >
        {/if}
        {#each mail.files as file (file.name)}
          <span class="chip"
            >{file.name} · {file.events}
            <button
              type="button"
              aria-label={`Remove ${file.name}`}
              disabled={mailBusy}
              onclick={() => mailCall("purchases_remove", { name: file.name })}
              >×</button
            ></span
          >
        {/each}
        <Button size="sm" onclick={() => (showSources = !showSources)}
          >{showSources ? "Show what was found" : "Add a source"}</Button
        >
        <Button
          size="sm"
          disabled={mailBusy || !mail.found.subscriptions.length}
          onclick={keepFound}>Add found subscriptions to my list</Button
        >
        {#if mail.connected}
          <Button
            size="sm"
            variant="ghost"
            disabled={mailBusy}
            onclick={() => mailCall("mail_disconnect")}>Disconnect Gmail</Button
          >
        {/if}
        {#if mailNote}<span class="note" role="status">{mailNote}</span>{/if}
        {#if mailError}<span class="error" role="alert">{mailError}</span>{/if}
      </div>
    {/if}
    {#if mail?.found && !showSources}
      <div class="panels mailpanels">
        {#each mailPanels as panel (panel.title)}
          <AnalyticPanel {panel} fill />
        {/each}
      </div>
    {:else}
      <div class="pane">
        <p class="hint lead">
          Find every subscription, purchase and sale from the places that know
          about them. Use one or all of these; what they find is put together
          below. Everything is read on this computer and nothing is changed.
        </p>
        <div class="sources">
          <form
            class="plans connect source"
            onsubmit={connectMail}
            aria-label="Connect Gmail"
          >
            <h4>Gmail receipts</h4>
            {#if mail?.connected}
              <p class="hint">
                Connected: <b>{mail.account}</b>. Receipts and account notices
                are read; adverts, newsletters and Promotions are left out.
              </p>
              <Button
                size="sm"
                variant="primary"
                disabled={mailBusy}
                onclick={async () => {
                  await mailCall("mail_scan");
                  if (!mailError) showSources = false;
                }}>{mailBusy ? "Scanning…" : "Scan now"}</Button
              >
            {:else}
              <p class="hint">
                Apple, Google Play, Netflix, Spotify and almost every shop email
                a receipt for each charge, renewal and cancellation. Only real
                receipts count: adverts and Promotions are left out.
              </p>
              <ol class="hint steps">
                <li>
                  Turn on 2-Step Verification, then make an app password.
                  <Button
                    size="sm"
                    onclick={() =>
                      openLink("https://myaccount.google.com/apppasswords")}
                    >Open App passwords</Button
                  >
                </li>
                <li>Paste your Gmail address and that app password.</li>
              </ol>
              <label
                >Gmail address <input
                  type="email"
                  autocomplete="off"
                  placeholder="you@gmail.com"
                  bind:value={mailForm.email}
                /></label
              >
              <label
                >App password <input
                  type="password"
                  autocomplete="off"
                  placeholder="16 letters"
                  bind:value={mailForm.password}
                /></label
              >
              <Button
                type="submit"
                variant="primary"
                disabled={mailBusy ||
                  !mailForm.email.trim() ||
                  !mailForm.password.trim()}
                >{mailBusy
                  ? "Connecting and scanning…"
                  : "Connect and scan"}</Button
              >
              {#if mail?.network && !["converse", "open"].includes(mail.network)}
                <p class="error">
                  The network is {mail.network}, so email cannot be read. Change
                  it in Settings, Agents.
                </p>
              {/if}
            {/if}
          </form>
          <section class="plans connect source" aria-label="Apple">
            <h4>Apple (App Store, iCloud, Apple Music)</h4>
            <p class="hint">
              Apple lets no other app read your account. Ask Apple for a copy of
              your data: on privacy.apple.com choose "Request a copy of your
              data" and tick "Apple Media Services information". Apple emails a
              link within a few days; add the .zip here.
            </p>
            <div class="row">
              <Button
                size="sm"
                onclick={() => openLink("https://privacy.apple.com/")}
                >Ask Apple for my data</Button
              >
              <Button
                size="sm"
                onclick={() =>
                  openLink("https://apps.apple.com/account/subscriptions")}
                >See Apple subscriptions</Button
              >
            </div>
            <Button
              size="sm"
              disabled={mailBusy}
              onclick={() => picker?.click()}>Add Apple's file</Button
            >
          </section>
          <section class="plans connect source" aria-label="Google Play">
            <h4>Google Play</h4>
            <p class="hint">
              Google Takeout gives you your Play subscriptions, orders and
              purchases. Only "Google Play Store" is ticked by the link below;
              it is ready in minutes. Add the .zip here.
            </p>
            <div class="row">
              <Button
                size="sm"
                onclick={() =>
                  openLink(
                    "https://takeout.google.com/settings/takeout/custom/play",
                  )}>Open Google Takeout</Button
              >
              <Button
                size="sm"
                onclick={() =>
                  openLink(
                    "https://play.google.com/store/account/subscriptions",
                  )}>See Play subscriptions</Button
              >
            </div>
            <Button
              size="sm"
              disabled={mailBusy}
              onclick={() => picker?.click()}>Add Google's file</Button
            >
          </section>
          <section class="plans connect source" aria-label="Bank statement">
            <h4>Bank or card statement</h4>
            <p class="hint">
              Catches what never emails a receipt. Download a few months of your
              statement as CSV from your bank's website or app. Anything charged
              every week, month or year for about the same amount is found as a
              subscription.
            </p>
            <Button
              size="sm"
              disabled={mailBusy}
              onclick={() => picker?.click()}>Add a statement</Button
            >
          </section>
        </div>
        {#if mailNote && !mail?.found}<p class="note" role="status">
            {mailNote}
          </p>{/if}
        {#if mailError && !mail?.found}<p class="error" role="alert">
            {mailError}
          </p>{/if}
      </div>
    {/if}
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
          The ones found in your receipts and added files are filled in for you,
          marked "found for you"; add any others here. Cancel opens the store's
          own page, where you sign in and make the change; then mark it here.
        </p>
        {#if subError}<p class="error" role="alert">{subError}</p>{/if}
        <ul class="sublist" aria-label="Active subscriptions">
          {#each live as row, i (`${i}:${row.name}`)}
            <li>
              <span class="subname"
                ><b>{row.name}</b>
                <span class="note"
                  >{row.store_name || STORE[row.store]} · {row.currency &&
                  row.currency !== report.currency
                    ? inCurrency(row.price, row.currency)
                    : money(row.price)}
                  {PER[row.period]}{row.renews
                    ? ` · renews ${row.renews}`
                    : ""}{row.auto ? " · found for you" : ""}</span
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
                  onclick={() => removeSub(row)}
                  >{row.auto ? "Hide" : "Remove"}</Button
                >
              </span>
            </li>
          {:else}
            <li class="note">No active subscription added or found yet.</li>
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
          Where your money comes in and goes out. From your receipts and
          statements, each wallet shows what came in and went out this month,
          which subscriptions it pays for and, with its balance entered, how
          many months those are covered. Services seen in your receipts are
          added for you. Balances can't be read by any app, so type them in.
        </p>
        {#if walletError}<p class="error" role="alert">{walletError}</p>{/if}
        <ul class="sublist" aria-label="Your wallets">
          {#each report.wallets as row, i (`${i}:${row.name}`)}
            <li>
              <span class="subname"
                ><b>{row.name}</b>
                <span class="note"
                  >{KIND[row.kind]} · {row.updated || !row.auto
                    ? inCurrency(row.balance, row.currency)
                    : "balance not entered"}{row.updated
                    ? ` · as of ${row.updated}`
                    : ""}{row.auto ? " · found for you" : ""}</span
                >
                {#if row.moves}
                  <span class="note"
                    >In this month {inCurrency(
                      row.received_month,
                      row.currency,
                    )} · this year {inCurrency(row.received_year, row.currency)} ·
                    out this month {inCurrency(row.spent_month, row.currency)} · last
                    {row.last}</span
                  >
                {/if}
                {#if row.pays_for.length}
                  <span class="note"
                    >Pays for {row.pays_for.join(", ")} ({inCurrency(
                      row.pays_monthly,
                      row.currency,
                    )} a month){row.covers_months !== null
                      ? ` · balance covers ${row.covers_months} months`
                      : ""}</span
                  >
                {/if}</span
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
                  onclick={() => removeWallet(row)}
                  >{row.auto ? "Hide" : "Remove"}</Button
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
          tokens it pays for. AI plans found in your receipts are listed below;
          they already count on the Overview.
        </p>
        {#if report.rows.some((r) => r.auto)}
          <ul class="sublist" aria-label="Plans found for you">
            {#each report.rows.filter((r) => r.auto) as row (row.name)}
              <li>
                <span class="subname"
                  ><b>{row.name}</b>
                  <span class="note"
                    >Found for you · {row.currency &&
                    row.currency !== report.currency
                      ? inCurrency(row.monthly, row.currency)
                      : money(row.monthly)} a month{row.provider_name
                      ? ` · ${row.provider_name}`
                      : ""}</span
                  ></span
                >
                <span class="buttons">
                  <Button size="sm" onclick={() => keepPlan(row)}>Keep</Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    aria-label={`Hide ${row.name}`}
                    onclick={() => hide(row.name)}>Hide</Button
                  >
                </span>
              </li>
            {/each}
          </ul>
        {/if}
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

  .mailbar {
    display: flex;
    flex-wrap: wrap;
    gap: var(--space-2);
    align-items: center;
    margin-top: var(--space-3);
  }

  .chip {
    display: inline-flex;
    gap: var(--space-1);
    align-items: center;
    padding: 2px var(--space-2);
    font-size: 0.75rem;
    border: 1px solid var(--color-border);
    border-radius: var(--radius-sm);
  }

  .chip button {
    padding: 0 2px;
    color: inherit;
    cursor: pointer;
    background: none;
    border: 0;
  }

  /* The four places subscriptions are found, side by side when there is room. */
  .sources {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
    gap: var(--space-3);
    margin-top: var(--space-3);
  }

  .source {
    display: flex;
    flex-direction: column;
    gap: var(--space-2);
    align-content: start;
  }

  .source label {
    display: grid;
    gap: 2px;
  }

  .lead {
    margin: var(--space-3) 0 0;
  }

  .steps {
    display: grid;
    gap: var(--space-2);
    margin: 0;
    padding-inline-start: var(--space-5);
  }

  /* Four lists in two rows: subscriptions and purchases, then sales and refunds. */
  .mailpanels {
    grid-template-rows: repeat(2, minmax(0, 1fr));
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

  /* A third panel (spend from receipts) takes the whole last row. */
  .panels > :global(:nth-child(3):last-child) {
    grid-column: 1 / -1;
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
