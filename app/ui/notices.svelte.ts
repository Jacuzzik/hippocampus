// Errors the user should see: a short message in the corner of the window, one per problem.
// The same problem is shown once, not on every retry, and the list never grows past three.

import { errorText } from "./crashLog.svelte.ts";

export type Notice = { id: number; what: string; detail: string };

const SHOWN_MS = 8000;
// A timer that keeps failing would show the same line again and again; one a minute is enough.
const REPEAT_MS = 60000;
const LIMIT = 3;

let list = $state<Notice[]>([]);
let nextId = 1;
const lastShown: Record<string, number> = {};

function dismiss(id: number): void {
  list = list.filter((notice) => notice.id !== id);
}

/**
 * Says that something failed: in the console for the developer and on screen for the user.
 * `what` is a full sentence in plain words ("Could not save the agents"); `cause` is what was thrown.
 */
export function report(what: string, cause: unknown): void {
  console.error(what, cause);
  const now = Date.now();
  if (now - (lastShown[what] ?? -REPEAT_MS) < REPEAT_MS) return;
  lastShown[what] = now;
  const detail = errorText(cause);
  const notice = { id: nextId++, what, detail: detail === what ? "" : detail };
  list = [...list, notice].slice(-LIMIT);
  setTimeout(() => dismiss(notice.id), SHOWN_MS);
}

export const notices = {
  get list(): Notice[] {
    return list;
  },
  dismiss,
};
