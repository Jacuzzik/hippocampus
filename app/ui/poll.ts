// One helper for every background refresh. It skips ticks while the window is hidden,
// so a minimised app does not keep asking the sidecar, and catches up once it is shown again.

/** Runs `task` every `ms` while the window is visible. Returns the function that stops it. */
export function every(task: () => unknown, ms: number): () => void {
  let missed = false;
  const run = (): void => {
    if (document.hidden) {
      missed = true;
      return;
    }
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
