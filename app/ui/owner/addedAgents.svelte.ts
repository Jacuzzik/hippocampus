// Agents the user created in the add-agent form. The sidecar keeps them in storage/agents.json;
// localStorage mirrors the list and is what loads when the sidecar cannot answer.
import { invoke } from "@tauri-apps/api/core";
import type { AgentDraft } from "../control/model";

// The note is private to the user: it is shown only in the card's menu dialog.
export type SavedAgent = AgentDraft & { id: string; note?: string };

const KEY = "hippocampus.addedAgents";

function readLocal(): SavedAgent[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "[]");
  } catch (cause) {
    console.error("Could not read the saved agents", cause);
    return [];
  }
}

function writeLocal(list: SavedAgent[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(list));
  } catch (cause) {
    console.error("Could not save the agents", cause);
  }
}

// Sends the whole list to the sidecar. The local copy is written first, so a failed call loses nothing.
async function persist(list: SavedAgent[]): Promise<void> {
  writeLocal(list);
  try {
    await invoke("sidecar_call", {
      method: "save_agents",
      params: { agents: list },
    });
  } catch (cause) {
    console.error("Could not save the agents to the sidecar", cause);
  }
}

export const addedAgents = $state<{ list: SavedAgent[] }>({
  list: readLocal(),
});

// Archived agent ids: hidden from the bottom bar, kept on this machine only.
const ARCHIVE_KEY = "hippocampus.archivedAgents";

function readArchived(): string[] {
  try {
    return JSON.parse(localStorage.getItem(ARCHIVE_KEY) ?? "[]");
  } catch (cause) {
    console.error("Could not read the archived agents", cause);
    return [];
  }
}

export const archived = $state<{ ids: string[] }>({ ids: readArchived() });

export function setArchived(id: string, on: boolean): void {
  archived.ids = on
    ? [...archived.ids.filter((x) => x !== id), id]
    : archived.ids.filter((x) => x !== id);
  try {
    localStorage.setItem(ARCHIVE_KEY, JSON.stringify(archived.ids));
  } catch (cause) {
    console.error("Could not save the archived agents", cause);
  }
}

// Set once the user changes the list, so a slow load never overwrites a newer agent.
let changed = false;

async function load(): Promise<void> {
  try {
    const { agents } = await invoke<{ agents: SavedAgent[] }>("sidecar_call", {
      method: "agents",
    });
    if (changed) return;
    if (agents.length === 0 && addedAgents.list.length > 0) {
      await persist(addedAgents.list); // first run with the sidecar: move the local list over
      return;
    }
    addedAgents.list = agents;
    writeLocal(agents);
  } catch (cause) {
    console.error(
      "Could not load the agents from the sidecar; using the local copy",
      cause,
    );
  }
}
void load();

export function addAgent(draft: AgentDraft): SavedAgent {
  const agent = { ...draft, id: crypto.randomUUID() };
  setAddedAgents([...addedAgents.list, agent]);
  // Each agent gets its own Claude Code session at setup; the sidecar keeps it across restarts.
  invoke("sidecar_call", { method: "agent_session", params: { agent: agent.id } }).catch((cause) =>
    console.error("Could not create the agent's session", cause),
  );
  return agent;
}

export function setAddedAgents(list: SavedAgent[]): void {
  changed = true;
  addedAgents.list = list;
  void persist(list);
}

// The card the user clicked; its panel shows in the right panel. Null when none is selected.
export const selection = $state<{ id: string | null }>({ id: null });

export function selectAgent(id: string | null): void {
  selection.id = id;
}

// The rename or note dialog, opened from the card menu or the agent panel. Its markup lives in AgentBar.
export const agentEdit = $state<{
  current: { id: string; mode: "rename" | "note"; value: string } | null;
}>({ current: null });

export function startEdit(id: string, mode: "rename" | "note"): void {
  const agent = addedAgents.list.find((a) => a.id === id);
  if (!agent) return;
  agentEdit.current = {
    id,
    mode,
    value: mode === "rename" ? agent.name : (agent.note ?? ""),
  };
}

export function saveEdit(): void {
  const edit = agentEdit.current;
  if (!edit) return;
  const { id, mode, value } = edit;
  setAddedAgents(
    addedAgents.list.map((a) =>
      a.id !== id
        ? a
        : mode === "rename"
          ? { ...a, name: value.trim() || a.name }
          : { ...a, note: value },
    ),
  );
  agentEdit.current = null;
}

export function archiveAgent(id: string): void {
  setArchived(id, true);
  if (selection.id === id) selection.id = null;
}

export function removeAgent(id: string): void {
  setAddedAgents(addedAgents.list.filter((a) => a.id !== id));
  if (selection.id === id) selection.id = null;
}
