// Agents the user created in the add-agent form. Kept in the webview's localStorage:
// no sidecar call exists for agents yet, so this is the only store (not the sidecar).
import type { AgentDraft } from "../control/model";

export type SavedAgent = AgentDraft & { id: string };

const KEY = "hippocampus.addedAgents";

function load(): SavedAgent[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "[]");
  } catch (cause) {
    console.error("Could not read the saved agents", cause);
    return [];
  }
}

function save(list: SavedAgent[]): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(list));
  } catch (cause) {
    console.error("Could not save the agents", cause);
  }
}

export const addedAgents = $state<{ list: SavedAgent[] }>({ list: load() });

export function addAgent(draft: AgentDraft): SavedAgent {
  const agent = { ...draft, id: crypto.randomUUID() };
  addedAgents.list = [...addedAgents.list, agent];
  save(addedAgents.list);
  return agent;
}

export function setAddedAgents(list: SavedAgent[]): void {
  addedAgents.list = list;
  save(list);
}
