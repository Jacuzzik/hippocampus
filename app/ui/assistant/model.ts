// Pure chat state: messages, tool log, confirm cards and the orb state. No DOM or Tauri, so it runs under node --test.

export type OrbState = "idle" | "listening" | "thinking" | "speaking";
export type ToolStatus =
  "requested" | "running" | "done" | "declined" | "failed";

export interface Message {
  role: "user" | "assistant" | "error";
  text: string;
}

export interface ToolEntry {
  call: string;
  name: string;
  tier: string;
  status: ToolStatus;
}

export interface ConfirmCard {
  call: string;
  name: string;
  tier: string;
  preview: string;
}

export interface Chat {
  /** The chat whose events are shown; null when no chat is running. */
  chatId: number | null;
  messages: Message[];
  tools: ToolEntry[];
  confirms: ConfirmCard[];
  orb: OrbState;
}

/** Events the sidecar prints while a chat runs (see core/__main__.py). */
export type SidecarEvent =
  | {
      event: "tool";
      chat: number;
      call: string;
      name: string;
      tier: string;
      status: ToolStatus;
    }
  | {
      event: "confirm";
      chat: number;
      call: string;
      name: string;
      tier: string;
      preview: string;
    };

/** The tool log keeps this many entries; older ones drop off. */
export const TOOL_LOG_LIMIT = 50;

export function emptyChat(): Chat {
  return { chatId: null, messages: [], tools: [], confirms: [], orb: "idle" };
}

export function sendMessage(chat: Chat, text: string, chatId: number): Chat {
  return {
    ...chat,
    chatId,
    messages: [...chat.messages, { role: "user", text }],
    confirms: [],
    orb: "thinking",
  };
}

export function receiveEvent(chat: Chat, event: SidecarEvent): Chat {
  if (event.chat !== chat.chatId) return chat;
  if (event.event === "confirm") {
    const card: ConfirmCard = {
      call: event.call,
      name: event.name,
      tier: event.tier,
      preview: event.preview,
    };
    return { ...chat, confirms: [...chat.confirms, card], orb: "listening" };
  }
  const entry: ToolEntry = {
    call: event.call,
    name: event.name,
    tier: event.tier,
    status: event.status,
  };
  const existing = chat.tools.some(
    (tool) => tool.call === event.call && tool.name === event.name,
  );
  const tools = existing
    ? chat.tools.map((tool) => (tool.call === event.call ? entry : tool))
    : [...chat.tools, entry].slice(-TOOL_LOG_LIMIT);
  // A tool that starts, or is declined, has been answered: its confirm card goes.
  const answered = event.status === "running" || event.status === "declined";
  const confirms = answered
    ? chat.confirms.filter((c) => c.call !== event.call)
    : chat.confirms;
  return {
    ...chat,
    tools,
    confirms,
    orb: confirms.length > 0 ? "listening" : "thinking",
  };
}

export type ChatResult = { reply: string; stopped: boolean };

export function finishChat(chat: Chat, result: ChatResult): Chat {
  const message: Message | null = result.stopped
    ? { role: "error", text: "Stopped." }
    : result.reply
      ? { role: "assistant", text: result.reply }
      : null;
  return {
    ...chat,
    chatId: null,
    messages: message ? [...chat.messages, message] : chat.messages,
    confirms: [],
    orb: message && !result.stopped ? "speaking" : "idle",
  };
}

export function failChat(chat: Chat, error: string): Chat {
  return {
    ...chat,
    chatId: null,
    messages: [...chat.messages, { role: "error", text: error }],
    confirms: [],
    orb: "idle",
  };
}

export function removeConfirm(chat: Chat, call: string): Chat {
  return { ...chat, confirms: chat.confirms.filter((c) => c.call !== call) };
}

/** Speaking is shown briefly after a reply, then the orb goes idle. */
export function settleSpeaking(chat: Chat): Chat {
  return chat.orb === "speaking" ? { ...chat, orb: "idle" } : chat;
}

export const ORB_LABELS: Record<OrbState, string> = {
  idle: "Idle",
  listening: "Waiting for you",
  thinking: "Thinking",
  speaking: "Replied",
};
