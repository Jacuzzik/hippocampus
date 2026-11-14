// Every keyboard shortcut in the app, in one list. Settings, Keyboard shows this table,
// so a shortcut that is added here is documented at the same time.

export type Shortcut = { keys: string; does: string; where: string };

export const SHORTCUTS: Shortcut[] = [
  { keys: "Ctrl+P", does: "Open the command palette", where: "Anywhere" },
  { keys: "Ctrl+O", does: "Jump to a note by name", where: "Anywhere" },
  { keys: "Ctrl+F", does: "Search the notes", where: "Anywhere" },
  { keys: "Ctrl+,", does: "Open Settings", where: "Anywhere" },
  { keys: "F11", does: "Full screen layout on or off", where: "Anywhere" },
  { keys: "Esc", does: "Close the open dialog", where: "Dialogs" },
  { keys: "Tab", does: "Move to the next control", where: "Dialogs" },
  { keys: "Enter", does: "Send the message", where: "Message boxes" },
  { keys: "Shift+Enter", does: "Add a line", where: "Message boxes" },
  { keys: "↑ ↓", does: "Move through the list", where: "Command palette" },
  { keys: "Enter", does: "Run the chosen entry", where: "Command palette" },
];
