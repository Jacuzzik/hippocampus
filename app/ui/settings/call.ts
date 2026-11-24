import { invoke } from "@tauri-apps/api/core";

// One backend call, for the sections that were Planned. Errors come back as the backend's own sentence.
// Each section that uses it keeps its own busy flag, so a control is disabled while its call runs.
export function call<T>(
  method: string,
  params: Record<string, unknown> = {},
): Promise<T> {
  return invoke<T>("sidecar_call", { method, params });
}

// A file the user picked, as base64, for calls that take a file.
export async function fileBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let text = "";
  for (let i = 0; i < bytes.length; i += 0x8000)
    text += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  return btoa(text);
}
