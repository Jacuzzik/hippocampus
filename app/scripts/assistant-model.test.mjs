// Tests for ui/assistant/model.ts. Node 24 strips the types when it imports the .ts file.
import assert from "node:assert/strict";
import { test } from "node:test";
import {
  emptyChat,
  failChat,
  finishChat,
  logActivity,
  receiveEvent,
  removeAsk,
  removeConfirm,
  sendMessage,
  settleSpeaking,
  TOOL_LOG_LIMIT,
} from "../ui/assistant/model.ts";

const write = (chat, call = "c1") => ({
  event: "confirm",
  chat: chat.chatId,
  call,
  name: "create_note",
  tier: "write",
  preview: "+new",
});

test("sending a message shows it and sets the orb to thinking", () => {
  const chat = sendMessage(emptyChat(), "hi", 1);
  assert.deepEqual(chat.messages, [{ role: "user", text: "hi" }]);
  assert.equal(chat.chatId, 1);
  assert.equal(chat.orb, "thinking");
});

test("a write waits for approval: listening, with a card that the answer removes", () => {
  let chat = sendMessage(emptyChat(), "make it", 1);
  chat = receiveEvent(chat, write(chat));
  assert.equal(chat.orb, "listening");
  assert.equal(chat.confirms.length, 1);
  chat = receiveEvent(chat, {
    event: "tool",
    chat: 1,
    call: "c1",
    name: "create_note",
    tier: "write",
    status: "running",
  });
  assert.equal(chat.confirms.length, 0);
  assert.equal(chat.orb, "thinking");
  assert.equal(chat.tools[0].status, "running");
});

test("a tool updates its own log entry rather than adding another", () => {
  let chat = sendMessage(emptyChat(), "x", 2);
  const tool = (status) => ({
    event: "tool",
    chat: 2,
    call: "c9",
    name: "read_note",
    tier: "read",
    status,
  });
  chat = receiveEvent(chat, tool("requested"));
  chat = receiveEvent(chat, tool("done"));
  assert.equal(chat.tools.length, 1);
  assert.equal(chat.tools[0].status, "done");
});

test("events for another chat are ignored", () => {
  const chat = sendMessage(emptyChat(), "x", 3);
  assert.equal(
    receiveEvent(chat, {
      event: "tool",
      chat: 99,
      call: "a",
      name: "n",
      tier: "read",
      status: "done",
    }),
    chat,
  );
});

test("the tool log keeps only the newest entries", () => {
  let chat = sendMessage(emptyChat(), "x", 4);
  for (let i = 0; i < TOOL_LOG_LIMIT + 5; i += 1) {
    chat = receiveEvent(chat, {
      event: "tool",
      chat: 4,
      call: `c${i}`,
      name: "read_note",
      tier: "read",
      status: "done",
    });
  }
  assert.equal(chat.tools.length, TOOL_LOG_LIMIT);
  assert.equal(chat.tools[0].call, "c5");
});

test("a finished reply is spoken briefly, then the orb settles to idle", () => {
  let chat = finishChat(sendMessage(emptyChat(), "hi", 5), {
    reply: "hello",
    stopped: false,
  });
  assert.deepEqual(chat.messages.at(-1), { role: "assistant", text: "hello" });
  assert.equal(chat.orb, "speaking");
  chat = settleSpeaking(chat);
  assert.equal(chat.orb, "idle");
});

test("a stopped chat says so and goes idle", () => {
  const chat = finishChat(sendMessage(emptyChat(), "hi", 6), {
    reply: "",
    stopped: true,
  });
  assert.deepEqual(chat.messages.at(-1), { role: "error", text: "Stopped." });
  assert.equal(chat.orb, "idle");
  assert.equal(chat.chatId, null);
});

test("an error ends the chat and keeps the message visible", () => {
  const chat = failChat(
    sendMessage(emptyChat(), "hi", 7),
    "could not reach localhost",
  );
  assert.deepEqual(chat.messages.at(-1), {
    role: "error",
    text: "could not reach localhost",
  });
  assert.equal(chat.orb, "idle");
});

test("declining removes the card", () => {
  let chat = sendMessage(emptyChat(), "x", 8);
  chat = receiveEvent(chat, { ...write(chat), chat: 8 });
  assert.equal(removeConfirm(chat, "c1").confirms.length, 0);
});

test("finishChat at the tool limit logs why it stopped and waits to continue", () => {
  const chat = finishChat(
    sendMessage(emptyChat(), "go", 6),
    { reply: "", stopped: false, limit: 20 },
    "09:30:00",
  );
  assert.equal(chat.chatId, null);
  assert.equal(chat.paused, 20);
  assert.equal(chat.orb, "idle");
  assert.deepEqual(chat.activity, [
    {
      at: "09:30:00",
      text: "Stopped after 20 tool calls in one request. Continue to let it go on.",
    },
  ]);
  assert.equal(chat.messages.at(-1).role, "user");
  assert.equal(sendMessage(chat, "Continue.", 7).paused, null);
});

test("logActivity keeps the newest entries, with their times", () => {
  let chat = emptyChat();
  for (let i = 0; i < TOOL_LOG_LIMIT + 5; i++)
    chat = logActivity(chat, `event ${i}`, "10:00:00");
  assert.equal(chat.activity.length, TOOL_LOG_LIMIT);
  assert.equal(chat.activity.at(-1).text, `event ${TOOL_LOG_LIMIT + 4}`);
  assert.equal(chat.activity[0].at, "10:00:00");
});

test("an ask from the assistant waits for an answer and clears when answered", () => {
  const chat = sendMessage(emptyChat(), "book a room", 1);
  const asked = receiveEvent(chat, {
    event: "ask",
    chat: 1,
    call: "a1",
    question: "Which day?",
  });
  assert.deepEqual(asked.asks, [{ call: "a1", question: "Which day?" }]);
  assert.equal(asked.orb, "listening");
  assert.equal(removeAsk(asked, "a1").asks.length, 0);
  assert.equal(
    finishChat(asked, { reply: "done", stopped: false }).asks.length,
    0,
  );
});

test("an ask from another chat is ignored", () => {
  const chat = sendMessage(emptyChat(), "hi", 1);
  const other = receiveEvent(chat, {
    event: "ask",
    chat: 2,
    call: "a1",
    question: "?",
  });
  assert.equal(other.asks.length, 0);
});
