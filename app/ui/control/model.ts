// Pure helpers for the control panel. No DOM or Tauri, so they run under node --test.

export const NETWORK_MODES = ["off", "listen", "converse", "open"] as const;
export type NetworkMode = (typeof NETWORK_MODES)[number];

export const NETWORK_TEXT: Record<NetworkMode, string> = {
  off: "Nothing leaves this machine. The default.",
  listen: "No outbound calls. Reserved for incoming connections.",
  converse: "Calls to the model provider you set up, and nothing else.",
  open: "Calls to the model provider and any other outbound call.",
};

export const WINDOWS = ["five_hour", "daily", "weekly", "monthly"] as const;
export type Window = (typeof WINDOWS)[number];

export const WINDOW_LABELS: Record<Window, string> = {
  five_hour: "5 hours",
  daily: "day",
  weekly: "week",
  monthly: "month",
};

export interface Caps {
  five_hour: number;
  daily: number;
  weekly: number;
  monthly: number;
}

/** A cap that is reached: the scope, window, tokens used and the cap. */
export interface Overrun {
  scope: string;
  window: Window;
  used: number;
  cap: number;
}

/** The first cap already reached, checked in window order. Caps of 0 are no cap. */
export function overrunOf(
  scope: string,
  caps: Caps,
  used: Caps,
): Overrun | null {
  for (const window of WINDOWS) {
    const cap = caps[window];
    if (cap > 0 && used[window] >= cap) {
      return { scope, window, used: used[window], cap };
    }
  }
  return null;
}

/** "1,250 of 5,000 tokens" for a cap, or "1,250 tokens, no cap" when the cap is 0. */
export function usageLine(used: number, cap: number): string {
  const format = (n: number) => n.toLocaleString("en-US");
  return cap > 0
    ? `${format(used)} of ${format(cap)} tokens`
    : `${format(used)} tokens, no cap`;
}

/** Cap text from an input: a whole number of 0 or more, or null when it is not one. */
export function parseCap(text: string): number | null {
  const trimmed = text.trim();
  if (trimmed === "") return 0;
  if (!/^\d+$/.test(trimmed)) return null;
  return Number(trimmed);
}

export type ActivityKind =
  "handoff" | "tool" | "approval" | "error" | "budget" | "setting";

export interface ActivityRow {
  ts: string;
  kind: ActivityKind;
  text?: string;
  tool?: string;
  tier?: string;
  status?: string;
  approved?: boolean;
  call?: string;
  method?: string;
}

export const ACTIVITY_FILTERS: { id: "all" | ActivityKind; label: string }[] = [
  { id: "all", label: "All" },
  { id: "handoff", label: "Handoffs" },
  { id: "tool", label: "Tool calls" },
  { id: "approval", label: "Approvals" },
  { id: "budget", label: "Budget" },
  { id: "error", label: "Errors" },
  { id: "setting", label: "Settings" },
];

export function filterActivity(
  rows: ActivityRow[],
  filter: "all" | ActivityKind,
): ActivityRow[] {
  return filter === "all" ? rows : rows.filter((row) => row.kind === filter);
}

/** One readable line for an activity row. Approvals say who decided. */
export function activityText(row: ActivityRow): string {
  if (row.kind === "approval") {
    const verdict = row.approved ? "approved" : "declined";
    return `${row.tool} (${row.tier}) ${verdict} by you on the approval card`;
  }
  if (row.kind === "tool") {
    return `${row.tool} (${row.tier}) ${row.status}`;
  }
  return row.text ?? row.method ?? row.kind;
}

/** A skill name as the sidecar accepts it: lowercase letters, digits and hyphens. */
export function isSkillName(name: string): boolean {
  return /^[a-z0-9][a-z0-9-]*$/.test(name);
}

/** The line that shows a saved key: its last four characters, never the whole key. */
export function keyStatus(saved: boolean, hint: string | null): string {
  if (!saved) return "Not set";
  return hint ? `Saved, ends in …${hint}` : "Saved";
}

// The Settings pages, in rail order. "words" are extra terms the search box matches.
export const SETTINGS_PAGES = [
  { id: "General", words: "vault folder last tab settings file" },
  {
    id: "Appearance",
    words: "motion animation terminal text size font theme light dark reset",
  },
  {
    id: "Agents",
    words:
      "engine provider model tool calls network autonomy shell sandbox rules bash",
  },
  { id: "Budgets", words: "tokens caps limits spend" },
  { id: "Models and keys", words: "api key secret provider claude openai" },
  {
    id: "Connectors",
    words:
      "integrations slack webhooks github notion calendar gmail drive mcp plugins ollama",
  },
  { id: "Memory", words: "memory search notes size" },
  { id: "Privacy and data", words: "error log telemetry remove data sign out" },
  {
    id: "Advanced",
    words:
      "backend sidecar logs log file feature switches flags dictation meeting prerequisites",
  },
  { id: "About", words: "version" },
] as const;
export type SettingsPage = (typeof SETTINGS_PAGES)[number]["id"];

export const AGENT_STEPS = [
  "Identity",
  "Workspace",
  "Engine",
  "Briefing",
] as const;

// kind: "key" needs a saved API key; "cli" runs a command-line tool the user must log in to; "local" runs on this computer.
export const AGENT_PROVIDERS = [
  { id: "claude", label: "Claude (Anthropic)", needsKey: true, kind: "key" },
  { id: "codex", label: "Codex (OpenAI CLI)", needsKey: false, kind: "cli" },
  {
    id: "gemini-cli",
    label: "Gemini CLI (Google)",
    needsKey: false,
    kind: "cli",
  },
  {
    id: "antigravity",
    label: "Antigravity (Google)",
    needsKey: false,
    kind: "cli",
  },
  {
    id: "ollama",
    label: "Ollama (on this computer)",
    needsKey: false,
    kind: "local",
  },
  { id: "openai", label: "OpenAI", needsKey: true, kind: "key" },
  { id: "xai", label: "xAI Grok", needsKey: true, kind: "key" },
  { id: "moonshot", label: "Moonshot Kimi", needsKey: true, kind: "key" },
  { id: "gemini", label: "Google Gemini (API)", needsKey: true, kind: "key" },
  { id: "qwen", label: "Alibaba Qwen", needsKey: true, kind: "key" },
  { id: "deepseek", label: "DeepSeek", needsKey: true, kind: "key" },
  { id: "mistral", label: "Mistral", needsKey: true, kind: "key" },
  { id: "groq", label: "Groq", needsKey: true, kind: "key" },
  { id: "openrouter", label: "OpenRouter", needsKey: true, kind: "key" },
] as const;

// Provider logos, by provider id. Providers with no file here show no logo.
// Plain Node (node --test) has no import.meta.glob, so the call throws there and the map stays empty.
let providerLogoFiles: Record<string, string> = {};
try {
  providerLogoFiles = import.meta.glob("../assets/provider-logos/*.svg", {
    eager: true,
    query: "?url",
    import: "default",
  }) as Record<string, string>;
} catch {
  /* no glob under node */
}
export const providerLogo = (id: string): string | undefined =>
  providerLogoFiles[`../assets/provider-logos/${id}.svg`];

// Model names shown as suggestions; the model field still accepts any name typed in.
// Claude: the project's Claude 5 list. Codex, Gemini, xAI, DeepSeek and Mistral: 2026 names from web sources, not checked against provider docs.
// Moonshot, Qwen, Groq and OpenRouter names are older and unverified for 2026.
export const AGENT_MODELS: Record<string, string[]> = {
  claude: [
    "claude-fable-5-1",
    "claude-opus-5-5",
    "claude-sonnet-5-5",
    "claude-haiku-5-5",
  ],
  codex: [
    "gpt-6.1-sol",
    "gpt-6.1-terra",
    "gpt-6-luna",
    "gpt-5.5",
    "gpt-5.4",
    "gpt-5.3-codex",
  ],
  // From `agy models` (Antigravity CLI), read 2026-11-07.
  antigravity: [
    "gemini-3.8-flash-high",
    "gemini-3.8-flash-medium",
    "gemini-3.8-flash-low",
    "claude-sonnet-4-6",
    "claude-opus-4-6-thinking",
    "gpt-oss-120b-medium",
  ],
  "gemini-cli": [
    "gemini-3.1-pro-preview",
    "gemini-3-flash-preview",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
  ],
  ollama: ["qwen2.5:1.5b"],
  openai: [
    "gpt-6.1-sol",
    "gpt-6.1-terra",
    "gpt-6-luna",
    "gpt-5.5",
    "gpt-5.4",
    "gpt-5.4-mini",
    "gpt-5.4-nano",
  ],
  xai: ["grok-4.6", "grok-4.5", "grok-4.3", "grok-latest"],
  moonshot: ["kimi-k3", "kimi-k2.6", "moonshot-v1-8k"],
  gemini: [
    "gemini-3.1-pro-preview",
    "gemini-3.1-flash-lite",
    "gemini-3-flash-preview",
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite",
  ],
  qwen: ["qwen3.8-max", "qwen3.7-plus", "qwen3.8-flash"],
  deepseek: ["deepseek-v4-pro", "deepseek-flash"],
  mistral: ["mistral-large-3", "mistral-small-4", "codestral-latest"],
  groq: [
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant",
    "openai/gpt-oss-120b",
  ],
  openrouter: [
    "anthropic/claude-sonnet-4.5",
    "openai/gpt-4o",
    "google/gemini-2.5-pro",
  ],
};

/** Card faces: one per card-face-XX.svg in ui/assets/faces-new. The id is the file name. */
let cardFaceUrls: Record<string, string> = {};
try {
  cardFaceUrls = import.meta.glob("../assets/faces-new/card-face-*.svg", {
    eager: true,
    query: "?url",
    import: "default",
  }) as Record<string, string>;
} catch {
  /* no glob under node */
}

export const CARD_FACES = Object.entries(cardFaceUrls)
  .map(([path, url]) => ({
    id: path.split("/").pop()?.replace(".svg", "") ?? path,
    url,
  }))
  .sort((a, b) => a.id.localeCompare(b.id));

/** Original 8x8 pixel avatars drawn here in code. "#" is a filled pixel, "." is empty. */
export const AVATARS = [
  {
    id: "pip",
    name: "Pip",
    rows: [
      "..####..",
      ".######.",
      "##.##.##",
      "########",
      "########",
      ".######.",
      "..#..#..",
      "..#..#..",
    ],
  },
  {
    id: "moss",
    name: "Moss",
    rows: [
      "...##...",
      "..####..",
      ".##..##.",
      ".######.",
      ".######.",
      "..####..",
      ".#.##.#.",
      "........",
    ],
  },
  {
    id: "ember",
    name: "Ember",
    rows: [
      "#......#",
      ".#....#.",
      "..####..",
      ".######.",
      ".#.##.#.",
      ".######.",
      "..####..",
      "........",
    ],
  },
  {
    id: "quill",
    name: "Quill",
    rows: [
      "...#....",
      "..###...",
      ".#####..",
      "#.###.#.",
      "#######.",
      ".#####..",
      "..#.#...",
      "........",
    ],
  },
] as const;

/** Jobs for the briefing step. Clicking one fills the description and the goal. */
export const AGENT_TEMPLATES = [
  {
    id: "janitor",
    label: "Repo janitor",
    description:
      "Keeps the repository tidy: stale branches, dead code and clutter.",
    goal: "Keep the repo lean so the team can find things fast. Remove stale branches, dead code and stray files each week and list what was removed.",
  },
  {
    id: "docs",
    label: "Docs writer",
    description: "Keeps the docs in step with the code.",
    goal: "Make sure every doc matches the code it describes. Update or flag any page whose content no longer matches the current behaviour.",
  },
  {
    id: "triage",
    label: "Bug triager",
    description: "Reads new bug reports and sorts them.",
    goal: "Get every new bug report into the right queue within a day. Read each one and file it under the correct area.",
  },
  {
    id: "research",
    label: "Research assistant",
    description: "Finds and summarises sources on a question.",
    goal: "Answer one question with the best sources available. Find credible sources and summarise what each says about it.",
  },
  {
    id: "release",
    label: "Release manager",
    description: "Prepares each release.",
    goal: "Ship each release on time with nothing missing. Run the checklist from freeze to publish and report any open item.",
  },
  {
    id: "tests",
    label: "Test writer",
    description: "Writes tests for untested code and keeps the suite green.",
    goal: "Raise confidence in the codebase. Find code without tests, write focused tests for it and make sure the full suite passes.",
  },
  {
    id: "deps",
    label: "Dependency updater",
    description: "Keeps packages current and flags breaking upgrades.",
    goal: "Stay secure and current. Update packages with patch and minor releases, and report major upgrades with the changes they need.",
  },
  {
    id: "security",
    label: "Security auditor",
    description: "Scans code and config for common security holes.",
    goal: "Find and report security problems before attackers do. Check for injection, exposed secrets and unsafe defaults, ranked by risk.",
  },
  {
    id: "review",
    label: "Code reviewer",
    description: "Reviews each change for bugs, clarity and risk.",
    goal: "Catch problems before merge. Review each change for correctness and clarity, and leave specific, actionable comments.",
  },
  {
    id: "perf",
    label: "Performance tuner",
    description: "Finds slow code paths and measures the fixes.",
    goal: "Make the app faster where it matters. Profile the slowest paths, propose fixes, and measure before and after each change.",
  },
  {
    id: "a11y",
    label: "Accessibility checker",
    description: "Checks screens for contrast, labels and keyboard use.",
    goal: "Make the app usable for everyone. Check each screen for colour contrast, labels and keyboard navigation, and list each fix.",
  },
  {
    id: "i18n",
    label: "Translator",
    description: "Translates UI text and keeps language files in sync.",
    goal: "Make the app available in more languages. Translate new strings, keep every language file in step and flag missing keys.",
  },
  {
    id: "support",
    label: "Support drafter",
    description: "Drafts replies to customer questions for review.",
    goal: "Answer customers faster without losing the human touch. Draft a clear, polite reply to each question for a person to approve.",
  },
  {
    id: "inbox",
    label: "Inbox sorter",
    description: "Sorts incoming messages into folders and flags urgent ones.",
    goal: "Keep the inbox workable. Label each new message, flag urgent ones and draft replies for routine questions.",
  },
  {
    id: "notes",
    label: "Meeting summariser",
    description: "Turns meeting notes into decisions and action items.",
    goal: "Make sure nothing agreed in a meeting gets lost. Write the decisions, then each action item with its owner and due date.",
  },
  {
    id: "planner",
    label: "Sprint planner",
    description: "Breaks big tasks into small ones and estimates them.",
    goal: "Make the next sprint realistic. Split large tasks into small ones with estimates, and flag work too vague to start.",
  },
  {
    id: "metrics",
    label: "Metrics reporter",
    description: "Builds a short weekly report from the key numbers.",
    goal: "Give the team a weekly read on how things are going. Pull the key numbers, note what changed and why it matters.",
  },
  {
    id: "seo",
    label: "SEO checker",
    description: "Checks pages for titles, descriptions and broken links.",
    goal: "Help people find the site. Check each page's title, meta description and headings, and list fixes in priority order.",
  },
  {
    id: "onboard",
    label: "Onboarding guide",
    description: "Walks new team members through setup and first tasks.",
    goal: "Get new team members productive quickly. Give each newcomer the setup steps and a first task that teaches the codebase.",
  },
  {
    id: "data",
    label: "Data cleaner",
    description: "Finds and fixes duplicate, missing or malformed records.",
    goal: "Keep the data trustworthy. Find duplicate, empty or malformed records, fix the safe ones and list the rest for review.",
  },
] as const;

/** What the add-agent form collects. Empty strings are not yet answered. */
export interface AgentDraft {
  name: string;
  character: string;
  folder: string;
  provider: string;
  model: string;
  command: string;
  description: string;
  goal: string;
}

/** The first problem with a step, or null when the step can be left. */
export function agentStepError(step: number, draft: AgentDraft): string | null {
  if (step === 0 && draft.name.trim() === "") return "Give the agent a name.";
  if (step === 1 && draft.folder.trim() === "")
    return "Choose the folder the agent works in.";
  if (step === 2) {
    if (!AGENT_PROVIDERS.some((p) => p.id === draft.provider))
      return "Pick a provider.";
    if (draft.model.trim() === "") return "Name the model.";
  }
  return null;
}

/** A command-line tool's state from the sidecar's provider_status: installed, logged in (null when unknown), and the steps. */
export interface CliState {
  provider: string;
  label: string;
  installed: boolean;
  logged_in: boolean | null;
  steps: string;
}

/** "Ready" when the provider needs no key or a key is saved, else "Not set up" with the reason. */
export function engineStatus(
  provider: string,
  savedKeys: string[],
  clis: CliState[] = [],
  servers: { provider: string; running: boolean }[] = [],
): { ready: boolean; text: string } {
  const row = AGENT_PROVIDERS.find((p) => p.id === provider);
  if (!row) return { ready: false, text: "Not set up: pick a provider." };
  if (row.kind === "local") {
    const server = servers.find((s) => s.provider === provider);
    if (!server) return { ready: false, text: `Checking ${row.label}…` };
    return server.running
      ? { ready: true, text: `Ready: ${row.label} is running.` }
      : { ready: false, text: `Not running: start ${row.label} first.` };
  }
  if (row.kind === "cli") {
    const cli = clis.find((c) => c.provider === provider);
    if (!cli) return { ready: false, text: `Checking ${row.label}…` };
    if (cli.logged_in === true && cli.installed)
      return { ready: true, text: `Ready: ${row.label} is logged in.` };
    return {
      ready: false,
      text: cli.steps || `Not checked: log in to ${row.label} first.`,
    };
  }
  return savedKeys.includes(provider)
    ? { ready: true, text: `Ready: ${row.label} key saved.` }
    : { ready: false, text: `Not set up: no ${row.label} key saved.` };
}

/** The command line the choice builds, e.g. "claude --model m". */
export function agentCommand(
  draft: Pick<AgentDraft, "provider" | "model">,
): string {
  const model = draft.model.trim();
  if (draft.provider === "ollama") return `ollama run ${model}`;
  if (draft.provider === "codex") return `codex --model ${model}`;
  if (draft.provider === "gemini-cli") return `gemini --model ${model}`;
  if (draft.provider === "antigravity") return `agy --model ${model}`;
  // API providers have no command line: the app calls them directly with the saved key.
  if (draft.provider !== "claude") return "";
  return `claude --model ${model}`;
}

/** A dispatched task needs words in it. The agent is picked from the list the panel shows. */
export function dispatchError(agent: string, task: string): string | null {
  if (agent === "") return "Pick an agent.";
  if (task.trim() === "") return "Write the task.";
  return null;
}
