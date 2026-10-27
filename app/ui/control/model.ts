// Pure helpers for the control panel. No DOM or Tauri, so they run under node --test.

export const NETWORK_MODES = ["off", "listen", "converse", "open"] as const;
export type NetworkMode = (typeof NETWORK_MODES)[number];

export const NETWORK_TEXT: Record<NetworkMode, string> = {
  off: "Nothing leaves this machine. The default.",
  listen: "No outbound calls. Reserved for incoming connections.",
  converse: "Calls to the model provider you set up, and nothing else.",
  open: "Calls to the model provider and any other outbound call.",
};

export const WINDOWS = ["daily", "weekly", "monthly"] as const;
export type Window = (typeof WINDOWS)[number];

export interface Caps {
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
