// The assistant's live state, shared by the chat panel and the orb. Talks to the sidecar through the Tauri bridge.
import { invoke } from "@tauri-apps/api/core";
import { listen } from "@tauri-apps/api/event";
import {
  emptyChat,
  failChat,
  finishChat,
  receiveEvent,
  removeConfirm,
  sendMessage,
  settleSpeaking,
  type Chat,
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
  },

  async send(text: string): Promise<void> {
    const trimmed = text.trim();
    if (!trimmed || this.busy) return;
    const id = nextChatId++;
    chat = sendMessage(chat, trimmed, id);
    try {
      const result = await invoke<{ reply: string; stopped: boolean }>(
        "sidecar_call",
        {
          method: "chat",
          params: { chat: id, text: trimmed },
        },
      );
      chat = finishChat(chat, result);
    } catch (cause) {
      chat = failChat(chat, errorText(cause));
    }
    if (chat.orb === "speaking") {
      setTimeout(() => (chat = settleSpeaking(chat)), SPEAKING_MS);
    }
  },

  /** The kill switch: the sidecar halts pending tool calls and the model call. */
  async stop(): Promise<void> {
    try {
      await invoke("sidecar_call", { method: "stop" });
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
