// Pure helpers for the assistant tools dialog. No DOM or Tauri, so they run under node --test.

export interface ToolRow {
  name: string;
  tier: string;
  allowed: boolean;
}

/** The allowlist after one tool is ticked (on) or unticked (off). */
export function allowlistAfter(
  tools: ToolRow[],
  name: string,
  on: boolean,
): string[] {
  return tools
    .filter((tool) => (tool.name === name ? on : tool.allowed))
    .map((tool) => tool.name);
}
