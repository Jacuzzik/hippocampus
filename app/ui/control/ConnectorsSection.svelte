<script lang="ts">
  import { invoke } from "@tauri-apps/api/core";
  import { onMount } from "svelte";
  import StatusCard, { type CardStatus } from "../controls/StatusCard.svelte";

  // Everything the app can connect to, one card each. A connector that is not built yet still has a card
  // that says what it will do and what is missing, so nothing here is a dead end.
  type Card = {
    name: string;
    what: string;
    status: CardStatus;
    reason: string;
  };

  let webhooks = $state<number | null>(null);
  let jobs = $state<number | null>(null);
  let ollama = $state<string | null>(null);

  onMount(() => {
    invoke<{ webhooks: unknown[] }>("sidecar_call", {
      method: "webhooks",
    }).then(
      (r) => (webhooks = r.webhooks.length),
      () => (webhooks = null),
    );
    invoke<{ jobs: unknown[] }>("sidecar_call", { method: "jobs" }).then(
      (r) => (jobs = r.jobs.length),
      () => (jobs = null),
    );
    invoke<{ agents: { ollama: string } }>("sidecar_call", {
      method: "settings",
    }).then(
      (r) => (ollama = r.agents.ollama),
      () => (ollama = null),
    );
  });

  const count = (n: number | null, word: string): string =>
    n === null
      ? "Could not read the list."
      : `${n} ${word}${n === 1 ? "" : "s"} saved.`;

  const working = $derived<Card[]>([
    {
      name: "Webhooks",
      what: "A saved trigger that runs one local job after you approve it.",
      status: "Local only",
      reason: `${count(webhooks, "webhook")} Nothing listens on a network port yet, so no outside service can call them.`,
    },
    {
      name: "Scheduled jobs",
      what: "Notes jobs that run on a timer, such as the weekly link check.",
      status: "Local only",
      reason: `${count(jobs, "job")} Manage them in the Control panel, on the Work tab.`,
    },
    {
      name: "GitHub",
      what: "Open issues for an agent's folder, shown on the Monitor tab.",
      status: "Local only",
      reason:
        "Uses the gh command-line tool with your own login. The app stores no GitHub token.",
    },
    {
      name: "Local model (Ollama)",
      what: "Runs a model on this computer, with no key and no network.",
      status: "Local only",
      reason: ollama
        ? `Model: ${ollama}. The app does not yet check that Ollama is running.`
        : "The app does not yet check that Ollama is running.",
    },
  ]);

  const planned: Card[] = [
    {
      name: "Slack",
      what: "One bot that answers in chosen channels and replies in threads.",
      status: "Planned",
      reason: "Needs a token store and a message bridge in the backend.",
    },
    {
      name: "Inbound webhooks",
      what: "GitHub, Linear, Telegram or custom calls that land in an agent's inbox.",
      status: "Planned",
      reason: "Needs a listening address and a signing secret per webhook.",
    },
    {
      name: "MCP servers",
      what: "Extra tools for agents, read from each command-line tool's own config.",
      status: "Planned",
      reason: "The app does not read those config files yet.",
    },
    {
      name: "Plugins",
      what: "Bundles of skills and tools that install in one step.",
      status: "Planned",
      reason: "No plugin format is defined yet.",
    },
    {
      name: "Notion",
      what: "Read pages and databases into notes.",
      status: "Planned",
      reason: "Needs a browser sign-in and a token in the keychain.",
    },
    {
      name: "Google Calendar",
      what: "Show today's events in the daily brief.",
      status: "Planned",
      reason: "Needs a browser sign-in and a token in the keychain.",
    },
    {
      name: "Gmail",
      what: "Read-only search of your mail for an agent.",
      status: "Planned",
      reason: "Needs a browser sign-in and a token in the keychain.",
    },
    {
      name: "Google Drive",
      what: "Read documents into the vault.",
      status: "Planned",
      reason: "Needs a browser sign-in and a token in the keychain.",
    },
  ];
</script>

<section class="control-section" aria-labelledby="control-connectors">
  <h3 id="control-connectors">Connectors</h3>
  <p class="hint">
    What the app can reach today, and what is planned. Model keys are on the
    Models and keys page.
  </p>
  <h4>Working on this computer</h4>
  <div class="grid">
    {#each working as card (card.name)}
      <StatusCard {...card} />
    {/each}
  </div>
  <h4>Planned</h4>
  <div class="grid">
    {#each planned as card (card.name)}
      <StatusCard {...card} />
    {/each}
  </div>
</section>

<style>
  h4 {
    margin: var(--space-3) 0 var(--space-2);
    color: var(--color-text-muted);
    font-size: var(--font-size-xs);
    letter-spacing: 0.06em;
    text-transform: uppercase;
  }

  .grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
    gap: var(--space-2);
  }
</style>
