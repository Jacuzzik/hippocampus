// A local record of UI errors, so a failure leaves a trace instead of a blank panel.
// Kept in this window's storage only: nothing is sent anywhere.

export type CrashRow = { at: string; source: string; message: string };

const KEY = "hippocampus.crashLog";
const LIMIT = 50;

function read(): CrashRow[] {
  try {
    const rows: unknown = JSON.parse(localStorage.getItem(KEY) ?? "[]");
    return Array.isArray(rows) ? (rows as CrashRow[]).slice(-LIMIT) : [];
  } catch {
    return [];
  }
}

let rows = $state<CrashRow[]>(read());
// Errors seen since this window opened; the health bar shows this count.
let fresh = $state(0);

/** A short readable line for any thrown value. */
export function errorText(cause: unknown): string {
  if (cause instanceof Error) return cause.message || cause.name;
  return typeof cause === "string" ? cause : JSON.stringify(cause) ?? String(cause);
}

/** Records one error. Never throws: a broken log must not break the app. */
export function recordError(source: string, cause: unknown): void {
  // A one-off timestamp string, not reactive state, so a plain Date is right here.
  // eslint-disable-next-line svelte/prefer-svelte-reactivity
  const at = new Date().toISOString();
  const row = { at, source, message: errorText(cause).slice(0, 500) };
  rows = [...rows, row].slice(-LIMIT);
  fresh += 1;
  try {
    localStorage.setItem(KEY, JSON.stringify(rows));
  } catch {
    /* storage full or blocked: the row stays in memory */
  }
}

/** Catches errors that no component handled: thrown in handlers, timers and rejected promises. */
export function installGlobalHandlers(): void {
  window.addEventListener("error", (e) => recordError("window", e.error ?? e.message));
  window.addEventListener("unhandledrejection", (e) => recordError("promise", e.reason));
}

export const crashLog = {
  get rows(): CrashRow[] {
    return rows;
  },
  get fresh(): number {
    return fresh;
  },
  dismiss(): void {
    fresh = 0;
  },
};
