// One helper for every background refresh. It skips ticks while the window is hidden,
// so a minimised app does not keep asking the sidecar, and catches up once it is shown again.

// Quiet mode (Settings, Appearance): background refreshes run at one fifth of their speed.
export const QUIET_SLOWDOWN = 5;
let quiet = false;
export function setQuiet(on: boolean): void {
  quiet = on;
}

/** Runs `task` every `ms` while the window is visible. Returns the function that stops it. */
export function every(task: () => unknown, ms: number): () => void {
  let missed = false;
  let ticks = 0;
  const run = (): void => {
    if (document.hidden) {
      missed = true;
      return;
    }
    // In quiet mode only every fifth tick runs the task.
    if (quiet && ++ticks % QUIET_SLOWDOWN !== 0) return;
    task();
  };
  const onShow = (): void => {
    if (document.hidden || !missed) return;
    missed = false;
    task();
  };
  const timer = setInterval(run, ms);
  document.addEventListener("visibilitychange", onShow);
  return () => {
    clearInterval(timer);
    document.removeEventListener("visibilitychange", onShow);
  };
}
