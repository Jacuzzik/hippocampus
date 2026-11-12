// Switches for parts of the app that carry some risk, so one can be turned off from
// Settings > Advanced without a new build. Each flag gates something real; a flag is not a promise.
import { prefs } from "./prefs.svelte.ts";

export const FLAGS = [
  {
    id: "panelRefresh",
    name: "Live panel refresh",
    what: "Control Room panels (inbox, tasks, activity and the rest) read again every few seconds while open.",
  },
  {
    id: "connectors",
    name: "Connectors page",
    what: "Shows the Connectors page in Settings.",
  },
] as const;
export type FlagId = (typeof FLAGS)[number]["id"];

/** True unless the flag was switched off. Every flag starts on. */
export function flagOn(id: FlagId): boolean {
  return prefs.flags[id] !== false;
}

export function setFlag(id: FlagId, on: boolean): void {
  prefs.flags = { ...prefs.flags, [id]: on };
}
