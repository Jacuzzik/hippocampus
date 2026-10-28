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

export const AGENT_PROVIDERS = [
  { id: "claude", label: "Claude (Anthropic)", needsKey: true },
  { id: "ollama", label: "Ollama (on this computer)", needsKey: false },
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

/** "Ready" when the provider needs no key or a key is saved, else "Not set up" with the reason. */
export function engineStatus(
  provider: string,
  savedKeys: string[],
): { ready: boolean; text: string } {
  const row = AGENT_PROVIDERS.find((p) => p.id === provider);
  if (!row) return { ready: false, text: "Not set up: pick a provider." };
  if (!row.needsKey)
    return { ready: true, text: "Ready: runs on this computer." };
  return savedKeys.includes(provider)
    ? { ready: true, text: `Ready: ${row.label} key saved.` }
    : { ready: false, text: `Not set up: no ${row.label} key saved.` };
}

/** A dispatched task needs words in it. The agent is picked from the list the panel shows. */
export function dispatchError(agent: string, task: string): string | null {
  if (agent === "") return "Pick an agent.";
  if (task.trim() === "") return "Write the task.";
  return null;
}
