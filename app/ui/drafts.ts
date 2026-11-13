// An unsent message is kept in the window's own storage, so closing or reloading the window does not lose it.
// Nothing here leaves the computer. A storage that is full or blocked is ignored: the box simply starts empty.

const PREFIX = "hippocampus.draft.";

export function loadDraft(key: string): string {
  try {
    return localStorage.getItem(PREFIX + key) ?? "";
  } catch {
    return "";
  }
}

/** Keeps `text` under `key`; an empty text removes the entry, so a sent message is not restored. */
export function saveDraft(key: string, text: string): void {
  try {
    if (text) localStorage.setItem(PREFIX + key, text);
    else localStorage.removeItem(PREFIX + key);
  } catch {
    // Storage is full or blocked; the draft lives only until the window closes.
  }
}
