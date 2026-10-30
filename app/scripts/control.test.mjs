// Tests for ui/control/model.ts. Node 24 strips the types when it imports the .ts file.
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  ACTIVITY_FILTERS,
  AGENT_TEMPLATES,
  AVATARS,
  WINDOWS,
  agentCommand,
  WINDOW_LABELS,
  activityText,
  agentStepError,
  dispatchError,
  engineStatus,
  filterActivity,
  isSkillName,
  keyStatus,
  overrunOf,
  parseCap,
  usageLine,
} from "../ui/control/model.ts";

test("a cap is reached only when it is set and the usage meets it", () => {
  const caps = { five_hour: 0, daily: 100, weekly: 0, monthly: 0 };
  assert.equal(
    overrunOf("app", caps, {
      five_hour: 0,
      daily: 99,
      weekly: 500,
      monthly: 900,
    }),
    null,
  );
  assert.deepEqual(
    overrunOf("app", caps, { five_hour: 0, daily: 100, weekly: 0, monthly: 0 }),
    {
      scope: "app",
      window: "daily",
      used: 100,
      cap: 100,
    },
  );
});

test("usage reads as a fraction, or as no cap when the cap is 0", () => {
  assert.equal(usageLine(1250, 5000), "1,250 of 5,000 tokens");
  assert.equal(usageLine(42, 0), "42 tokens, no cap");
});

test("cap input accepts whole numbers, empty as no cap, and refuses the rest", () => {
  assert.equal(parseCap(" 250 "), 250);
  assert.equal(parseCap(""), 0);
  assert.equal(parseCap("-3"), null);
  assert.equal(parseCap("1.5"), null);
});

test("activity filters keep one kind, and approvals say who decided", () => {
  const rows = [
    {
      ts: "t1",
      kind: "approval",
      tool: "create_note",
      tier: "write",
      approved: true,
    },
    { ts: "t2", kind: "tool", tool: "read_note", tier: "read", status: "done" },
    { ts: "t3", kind: "error", method: "chat", text: "network is Off" },
  ];
  assert.equal(filterActivity(rows, "all").length, 3);
  assert.deepEqual(
    filterActivity(rows, "approval").map((r) => r.tool),
    ["create_note"],
  );
  assert.equal(
    activityText(rows[0]),
    "create_note (write) approved by you on the approval card",
  );
  assert.equal(activityText(rows[2]), "network is Off");
});

test("every activity kind the sidecar writes has a filter button", () => {
  // The kinds from KINDS in core/activity.py. A new kind needs a button here too.
  const kinds = ["handoff", "tool", "approval", "error", "budget", "setting"];
  const buttons = ACTIVITY_FILTERS.map((f) => f.id).filter(
    (id) => id !== "all",
  );
  assert.deepEqual([...buttons].sort(), [...kinds].sort());
});

test("skill names and key hints are safe to show", () => {
  assert.equal(isSkillName("tidy-notes"), true);
  assert.equal(isSkillName("../tidy"), false);
  assert.equal(isSkillName("Tidy"), false);
  assert.equal(keyStatus(true, "a1b2"), "Saved, ends in …a1b2");
  assert.equal(keyStatus(false, null), "Not set");
});

test("the budget has a five-hour window before the day", () => {
  assert.deepEqual(WINDOWS, ["five_hour", "daily", "weekly", "monthly"]);
  assert.equal(WINDOW_LABELS.five_hour, "5 hours");
  const caps = { five_hour: 40, daily: 0, weekly: 0, monthly: 0 };
  assert.deepEqual(
    overrunOf("assistant", caps, {
      five_hour: 40,
      daily: 0,
      weekly: 0,
      monthly: 0,
    }),
    {
      scope: "assistant",
      window: "five_hour",
      used: 40,
      cap: 40,
    },
  );
});

test("an agent step cannot be left until its answer is given", () => {
  const draft = {
    name: "",
    character: "",
    colour: "accent",
    folder: "",
    isolation: "shared",
    resume: false,
    provider: "claude",
    model: "",
    command: "",
    description: "",
    goal: "",
  };
  assert.equal(agentStepError(0, draft), "Give the agent a name.");
  assert.equal(agentStepError(0, { ...draft, name: "Ada" }), null);
  assert.equal(agentStepError(1, { ...draft, folder: "/vault" }), null);
  assert.equal(
    agentStepError(2, { ...draft, model: "claude-sonnet-5-5" }),
    null,
  );
  assert.equal(agentStepError(3, { ...draft, goal: "Tidy notes" }), null);
});

test("an engine is Not set up until its key is saved, and Ollama needs none", () => {
  assert.deepEqual(engineStatus("claude", []), {
    ready: false,
    text: "Not set up: no Claude (Anthropic) key saved.",
  });
  assert.equal(engineStatus("claude", ["claude"]).ready, true);
  assert.equal(engineStatus("ollama", []).ready, true);
});

test("a dispatch needs an agent and a task", () => {
  assert.equal(dispatchError("", "Tidy"), "Pick an agent.");
  assert.equal(dispatchError("helper", "  "), "Write the task.");
  assert.equal(dispatchError("helper", "Tidy"), null);
});

test("the command line follows the provider, model and autonomy", () => {
  const base = {
    provider: "claude",
    model: "claude-sonnet-5-5",
    autonomy: "auto",
  };
  assert.equal(
    agentCommand(base),
    "claude --model claude-sonnet-5-5 --permission-mode bypassPermissions",
  );
  assert.equal(
    agentCommand({ ...base, autonomy: "ask" }),
    "claude --model claude-sonnet-5-5 --permission-mode default",
  );
  assert.equal(
    agentCommand({ ...base, provider: "ollama", model: "qwen2.5" }),
    "ollama run qwen2.5",
  );
});

test("every avatar is an 8 by 8 grid and every template fills a briefing", () => {
  for (const avatar of AVATARS) {
    assert.equal(avatar.rows.length, 8, avatar.id);
    for (const row of avatar.rows) assert.match(row, /^[#.]{8}$/, avatar.id);
  }
  for (const t of AGENT_TEMPLATES) {
    assert.ok(t.description.length > 0 && t.goal.length > 0, t.id);
  }
});
