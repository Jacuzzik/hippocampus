// Desktop alerts (M.20): the backend sends {"event": "alert", "title", "body"} for an agent that
// crashed or tripped its circuit breaker, a question waiting and a new message for the user. The
// window shows one as a system notification only when alerts are on and the window is not in front.
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import { prefs } from "./prefs.svelte.ts";

type Alert = { event?: string; title?: string; body?: string };

/** Whether an alert should be shown now. Kept apart so it can be tested without a window. */
export function shouldAlert(
  payload: Alert,
  on: boolean,
  focused: boolean,
): payload is Required<Alert> {
  return (
    on &&
    !focused &&
    payload.event === "alert" &&
    typeof payload.title === "string" &&
    typeof payload.body === "string"
  );
}

export function watchAlerts(): () => void {
  let stop: (() => void) | undefined;
  let stopped = false;
  listen<Alert>("sidecar-event", (event) => {
    if (!shouldAlert(event.payload, prefs.alerts, document.hasFocus())) return;
    invoke("desktop_alert", {
      title: event.payload.title,
      body: event.payload.body,
    }).catch((cause) => console.error("Could not show a desktop alert", cause));
  }).then(
    (unlisten) => {
      if (stopped) unlisten();
      else stop = unlisten;
    },
    () => {
      /* no event bridge in a plain browser */
    },
  );
  return () => {
    stopped = true;
    stop?.();
  };
}
