// Panels read again when the backend says their data changed, instead of asking every few seconds.
// A slow timer stays as a safety net, for a change the backend did not announce.

import { listen } from "@tauri-apps/api/event";
import { every } from "./poll.ts";

/** Runs `task` shortly after the backend reports that `what` changed, and every `fallbackMs` besides. Returns the function that stops both. */
export function onChanged(
  what: string,
  task: () => unknown,
  fallbackMs = 30000,
): () => void {
  let timer: ReturnType<typeof setTimeout> | undefined;
  let unlisten: (() => void) | undefined;
  let stopped = false;
  listen<{ event?: string; what?: string }>("sidecar-event", (event) => {
    if (event.payload.event !== "changed" || event.payload.what !== what)
      return;
    // Several changes in a burst become one read.
    clearTimeout(timer);
    timer = setTimeout(task, 300);
  }).then(
    (stop) => {
      if (stopped) stop();
      else unlisten = stop;
    },
    () => {
      /* no event bridge (a plain browser): the slow timer still refreshes */
    },
  );
  const stopPoll = every(task, fallbackMs);
  return () => {
    stopped = true;
    clearTimeout(timer);
    unlisten?.();
    stopPoll();
  };
}
