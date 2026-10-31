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
  type Message,
  type SidecarEvent,
} from "./model";

/** How long the orb shows "speaking" after a reply. */
const SPEAKING_MS = 1500;
/** The agent this window talks to. Its Claude Code session is kept by the sidecar. */
const AGENT = "hippo";

/** One Claude Code session and the messages shown for it. */
export interface SavedSession {
  session: string;
  messages: Message[];
}

let chat = $state<Chat>(emptyChat());
let nextChatId = 1;
let started = false;
// Sessions oldest first; the last one is the current session.
let sessions = $state<SavedSession[]>([]);
// The index of the past session on screen, or null for the current one.
let viewing = $state<number | null>(null);

function errorText(cause: unknown): string {
  return cause instanceof Error ? cause.message : String(cause);
}

/** Save the sessions to the sidecar, so they survive a restart. Failures are logged, not shown. */
function persist(): void {
  if (sessions.length === 0) return;
  const last = sessions.length - 1;
  const saved = sessions.map((s, i) => (i === last && viewing === null ? { ...s, messages: chat.messages } : s));
  sessions = saved;
  invoke("sidecar_call", {
    method: "chat_history_save",
    params: { agent: AGENT, sessions: saved },
  }).catch((cause) => console.error("Could not save the chat history", cause));
}

export const assistant = {
  get chat(): Chat {
    return chat;
  },
  get busy(): boolean {
    return chat.chatId !== null;
  },
  /** Every session for this agent, oldest first. */
  get sessions(): SavedSession[] {
    return sessions;
  },
  /** Index of the session on screen, or null when it is the current one. */
  get viewing(): number | null {
    return viewing;
  },

  /** Listen for the sidecar's events and load the saved sessions. Call once, when the panel mounts. */
  async start(): Promise<void> {
    if (started) return;
    started = true;
    await listen<SidecarEvent>("sidecar-event", (event) => {
      chat = receiveEvent(chat, event.payload);
    });
    chat = logActivity(chat, "App started");
    try {
      const saved = await invoke<{ sessions: SavedSession[] }>("sidecar_call", {
        method: "chat_history",
        params: { agent: AGENT },
      });
      sessions = saved.sessions;
      if (sessions.length === 0) {
        const id = await invoke<{ session: string }>("sidecar_call", {
          method: "new_session",
          params: { agent: AGENT },
        });
        sessions = [{ session: id.session, messages: [] }];
      }
      chat = { ...chat, messages: (sessions[sessions.length - 1]?.messages ?? []) };
    } catch (cause) {
      console.error("Could not load the chat history", cause);
    }
  },

  /** Show a past session (read only). Ignored while a request runs. */
  showSession(index: number): void {
    if (this.busy || index < 0 || index >= sessions.length) return;
    viewing = index === sessions.length - 1 ? null : index;
    chat = { ...chat, messages: (sessions[index]?.messages ?? []) };
  },

  /** Go back to the current session. */
  showCurrent(): void {
    if (this.busy || viewing === null) return;
    viewing = null;
    chat = { ...chat, messages: (sessions[sessions.length - 1]?.messages ?? []) };
  },

  /** Start a new Claude Code session for this agent. The old one stays in the list. */
  async newSession(): Promise<void> {
    if (this.busy) return;
    this.showCurrent();
    try {
      const result = await invoke<{ session: string }>("sidecar_call", {
        method: "new_session",
        params: { agent: AGENT },
      });
      sessions = [...sessions, { session: result.session, messages: [] }];
      chat = { ...chat, messages: [] };
      persist();
    } catch (cause) {
      chat = failChat(chat, errorText(cause));
    }
  },

  /** Send a message. `resume` carries on a request that paused at the tool-call limit. */
  async send(text: string, resume = false): Promise<void> {
    const trimmed = text.trim();
    if (!trimmed || this.busy) return;
    this.showCurrent();
    const id = nextChatId++;
    chat = sendMessage(chat, trimmed, id);
    try {
      const result = await invoke<ChatResult>("sidecar_call", {
        method: "chat",
        params: { chat: id, text: trimmed, continue: resume, agent: AGENT },
      });
      chat = finishChat(chat, result);
    } catch (cause) {
      chat = failChat(chat, errorText(cause));
    }
    persist();
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
