import "@fontsource-variable/jetbrains-mono";
import "./styles/tokens.css";
import "./styles/global.css";
import { mount } from "svelte";
import App from "./App.svelte";
import { mockSidecar } from "../e2e/tauri-mock";

// Browser preview only (npm run dev in a normal browser): fake the desktop bridge with the test mock.
if (import.meta.env.DEV && !("__TAURI_INTERNALS__" in window)) {
  void mockSidecar({ addInitScript: (fn: () => void) => fn() });
}

const target = document.getElementById("app");
if (!target) {
  throw new Error("Missing #app mount point in index.html");
}

export default mount(App, { target });
