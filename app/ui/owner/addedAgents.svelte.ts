// Agents the user created in the add-agent form. The sidecar keeps them in storage/agents.json;
// localStorage mirrors the list and is what loads when the sidecar cannot answer.
import { invoke } from "@tauri-apps/api/core";
import type { AgentDraft } from "../control/model";

export type SavedAgent = AgentDraft & { id: string };

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
  return agent;
}

export function setAddedAgents(list: SavedAgent[]): void {
  changed = true;
  addedAgents.list = list;
  void persist(list);
}
