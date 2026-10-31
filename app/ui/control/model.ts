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

export const SETTINGS_TABS = [
  "General",
  "Prerequisites",
  "Autonomy and budgets",
  "Integrations",
  "Dictation and meeting",
  "Memory and knowledge",
] as const;
export type SettingsTab = (typeof SETTINGS_TABS)[number];

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
  { id: "gemini-cli", label: "Gemini CLI (Google)", needsKey: false, kind: "cli" },
  { id: "ollama", label: "Ollama (on this computer)", needsKey: false, kind: "local" },
  { id: "openai", label: "OpenAI", needsKey: true, kind: "key" },
  { id: "xai", label: "xAI Grok", needsKey: true, kind: "key" },
  { id: "moonshot", label: "Moonshot Kimi", needsKey: true, kind: "key" },
  { id: "gemini", label: "Google Gemini (API)", needsKey: true, kind: "key" },
  { id: "qwen", label: "Alibaba Qwen", needsKey: true, kind: "key" },
  { id: "deepseek", label: "DeepSeek", needsKey: true, kind: "key" },
  { id: "mistral", label: "Mistral", needsKey: true, kind: "key" },
  { id: "groq", label: "Groq", needsKey: true, kind: "key" },
  { id: "openrouter", label: "OpenRouter", needsKey: true, kind: "key" },
  { id: "lmstudio", label: "LM Studio (local)", needsKey: false, kind: "local" },
  { id: "vllm", label: "vLLM (local)", needsKey: false, kind: "local" },
] as const;

// Model names shown as suggestions; the model field still accepts any name typed in.
// Claude: the project's Claude 5 list. Codex, Gemini, xAI, DeepSeek and Mistral: 2026 names from web sources, not checked against provider docs.
// Moonshot, Qwen, Groq and OpenRouter names are older and unverified for 2026.
export const AGENT_MODELS: Record<string, string[]> = {
  claude: ["claude-fable-5-1", "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"],
  codex: ["gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.5", "gpt-5.4", "gpt-5.3-codex"],
  "gemini-cli": ["gemini-3.1-pro-preview", "gemini-3-flash-preview", "gemini-2.5-pro", "gemini-2.5-flash"],
  ollama: ["qwen2.5:1.5b"],
  openai: ["gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.5", "gpt-5.4", "gpt-5.4-mini", "gpt-5.4-nano"],
  xai: ["grok-4.6", "grok-4.5", "grok-4.3", "grok-latest"],
  moonshot: ["kimi-k3", "kimi-k2.6", "moonshot-v1-8k"],
  gemini: ["gemini-3.1-pro-preview", "gemini-3.1-flash-lite", "gemini-3-flash-preview", "gemini-2.5-pro", "gemini-2.5-flash", "gemini-2.5-flash-lite"],
  qwen: ["qwen-max", "qwen-plus", "qwen-turbo"],
  deepseek: ["deepseek-v4-pro", "deepseek-v4-flash"],
  mistral: ["mistral-large-3", "mistral-small-4", "codestral-latest"],
  groq: ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "qwen/qwen3-32b"],
  openrouter: ["anthropic/claude-sonnet-4.5", "openai/gpt-4o", "google/gemini-2.5-pro"],
  lmstudio: [],
  vllm: [],
};

/** Card faces: one per card-face-XX.svg in ui/assets/faces-new. The id is the file name. */
const cardFaceUrls = import.meta.glob("../assets/faces-new/card-face-*.svg", {
  eager: true,
  query: "?url",
  import: "default",
}) as Record<string, string>;

export const CARD_FACES = Object.entries(cardFaceUrls)
  .map(([path, url]) => ({ id: path.split("/").pop()?.replace(".svg", "") ?? path, url }))
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

export const AGENT_COLOURS = ["accent", "think", "confirm", "danger"] as const;

/** Briefing starters. They fill the description and goal; the name stays the user's. */
export const AGENT_TEMPLATES = [
  {
    id: "janitor",
    label: "Repo janitor",
    description:
      "Keeps the repository tidy: stale branches, dead code and clutter.",
    goal: "Find clutter each week and list it with a proposed fix. Delete nothing without a yes.",
  },
  {
    id: "docs",
    label: "Docs writer",
    description: "Keeps the docs in step with the code.",
    goal: "Update docs for any code change and flag the pages that no longer match.",
  },
  {
    id: "triage",
    label: "Bug triager",
    description: "Reads new bug reports and sorts them.",
    goal: "Label each new bug by area and severity, and ask for a repro when one is missing.",
  },
  {
    id: "research",
    label: "Research assistant",
    description: "Finds and summarises sources on a question.",
    goal: "Collect the best sources on the topic and write a short summary with links.",
  },
  {
    id: "release",
    label: "Release manager",
    description: "Prepares each release.",
    goal: "Draft the changelog, check the release checklist, and report anything blocking.",
  },
] as const;

/** What the add-agent form collects. Empty strings are not yet answered. */
export interface AgentDraft {
  name: string;
  character: string;
  colour: string;
  folder: string;
  isolation: "shared" | "own";
  resume: boolean;
  provider: string;
  model: string;
  command: string;
  /** "ask": it asks before acting; "auto": it acts on its own within its goal. */
  autonomy: "ask" | "auto";
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
  if (step === 3 && draft.goal.trim() === "")
    return "Say what the agent is for.";
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
): { ready: boolean; text: string } {
  const row = AGENT_PROVIDERS.find((p) => p.id === provider);
  if (!row) return { ready: false, text: "Not set up: pick a provider." };
  if (row.kind === "local")
    return { ready: true, text: "Ready: runs on this computer." };
  if (row.kind === "cli") {
    const cli = clis.find((c) => c.provider === provider);
    if (!cli) return { ready: false, text: `Checking ${row.label}…` };
    if (cli.logged_in === true && cli.installed)
      return { ready: true, text: `Ready: ${row.label} is logged in.` };
    return { ready: false, text: cli.steps || `Not checked: log in to ${row.label} first.` };
  }
  return savedKeys.includes(provider)
    ? { ready: true, text: `Ready: ${row.label} key saved.` }
    : { ready: false, text: `Not set up: no ${row.label} key saved.` };
}

/** The command line the choice builds, e.g. "claude --model m --permission-mode bypassPermissions". */
export function agentCommand(
  draft: Pick<AgentDraft, "provider" | "model" | "autonomy">,
): string {
  const model = draft.model.trim();
  if (draft.provider === "ollama") return `ollama run ${model}`;
  if (draft.provider === "codex") return `codex --model ${model}`;
  if (draft.provider === "gemini-cli") return `gemini --model ${model}`;
  // API providers have no command line: the app calls them directly with the saved key.
  if (draft.provider !== "claude") return "";
  const mode = draft.autonomy === "auto" ? "bypassPermissions" : "default";
  return `claude --model ${model} --permission-mode ${mode}`;
}

/** A dispatched task needs words in it. The agent is picked from the list the panel shows. */
export function dispatchError(agent: string, task: string): string | null {
  if (agent === "") return "Pick an agent.";
  if (task.trim() === "") return "Write the task.";
  return null;
}
