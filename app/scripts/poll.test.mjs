// Tests for ui/poll.ts, the one background-refresh helper. Time is faked; `document` is a small stand-in.
import assert from "node:assert/strict";
import { mock, test } from "node:test";
import { QUIET_SLOWDOWN, every, setQuiet } from "../ui/poll.ts";

function withWindow(hidden) {
  const listeners = new Map();
  globalThis.document = {
    hidden,
    addEventListener: (name, fn) => listeners.set(name, fn),
    removeEventListener: (name) => listeners.delete(name),
  };
  return listeners;
}

test("a task runs on every tick while the window is shown", () => {
  mock.timers.enable({ apis: ["setInterval"] });
  withWindow(false);
  setQuiet(false);
  let runs = 0;
  const stop = every(() => runs++, 1000);
  mock.timers.tick(5000);
  stop();
  assert.equal(runs, 5);
  mock.timers.reset();
});

test("in quiet mode a task runs once in every fifth tick", () => {
  mock.timers.enable({ apis: ["setInterval"] });
  withWindow(false);
  setQuiet(true);
  let runs = 0;
  const stop = every(() => runs++, 1000);
  mock.timers.tick(10_000);
  stop();
  setQuiet(false);
  assert.equal(runs, 10 / QUIET_SLOWDOWN);
  mock.timers.reset();
});

test("a hidden window skips the task and catches up when shown", () => {
  mock.timers.enable({ apis: ["setInterval"] });
  const listeners = withWindow(true);
  setQuiet(false);
  let runs = 0;
  const stop = every(() => runs++, 1000);
  mock.timers.tick(3000);
  assert.equal(runs, 0);
  globalThis.document.hidden = false;
  listeners.get("visibilitychange")();
  assert.equal(runs, 1);
  stop();
  mock.timers.reset();
});
