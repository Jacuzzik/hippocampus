// The assistant's live state, shared by the chat panel and the orb. Talks to the sidecar through the Tauri bridge.
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
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
  type Chat,
  type ChatResult,
  type SidecarEvent,
} from "./model";

/** How long the orb shows "speaking" after a reply. */
const SPEAKING_MS = 1500;

let chat = $state<Chat>(emptyChat());
let nextChatId = 1;
let started = false;

function errorText(cause: unknown): string {
  return cause instanceof Error ? cause.message : String(cause);
}

export const assistant = {
  get chat(): Chat {
    return chat;
  },
  get busy(): boolean {
    return chat.chatId !== null;
  },

  /** Listen for the sidecar's events. Call once, when the panel mounts. */
  async start(): Promise<void> {
    if (started) return;
    started = true;
    await listen<SidecarEvent>("sidecar-event", (event) => {
      chat = receiveEvent(chat, event.payload);
    });
    chat = logActivity(chat, "App started");
  },

  /** Send a message. `resume` carries on a request that paused at the tool-call limit. */
  async send(text: string, resume = false): Promise<void> {
    const trimmed = text.trim();
    if (!trimmed || this.busy) return;
    const id = nextChatId++;
    chat = sendMessage(chat, trimmed, id);
    try {
      const result = await invoke<ChatResult>("sidecar_call", {
        method: "chat",
        params: { chat: id, text: trimmed, continue: resume },
      });
      chat = finishChat(chat, result);
    } catch (cause) {
      chat = failChat(chat, errorText(cause));
    }
    if (chat.orb === "speaking") {
      setTimeout(() => (chat = settleSpeaking(chat)), SPEAKING_MS);
    }
  },

  /** Let the next request past a token cap, then send the last message again. */
  async allowOne(): Promise<void> {
    try {
      await invoke("sidecar_call", { method: "budget_allow" });
      chat = { ...chat, budgetPause: null };
    } catch (cause) {
      chat = failChat(chat, errorText(cause));
    }
  },

  /** Carry on after a pause at the tool-call limit. */
  async resume(): Promise<void> {
    await this.send("Continue.", true);
  },

  /** The kill switch: the sidecar halts pending tool calls and the model call. */
  async stop(): Promise<void> {
    try {
      await invoke("sidecar_call", { method: "stop" });
    } catch (cause) {
      chat = failChat(chat, errorText(cause));
    }
  },

  /** Send the user's answer to a question the assistant asked. */
  async answer(call: string, text: string): Promise<void> {
    chat = removeAsk(chat, call);
    try {
      await invoke("sidecar_call", {
        method: "answer",
        params: { call, text },
      });
    } catch (cause) {
      chat = failChat(chat, errorText(cause));
    }
  },

  async decide(call: string, approve: boolean): Promise<void> {
    chat = removeConfirm(chat, call);
    try {
      await invoke("sidecar_call", {
        method: "confirm",
        params: { call, approve },
      });
    } catch (cause) {
      chat = failChat(chat, errorText(cause));
    }
  },
};
