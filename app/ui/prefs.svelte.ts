// Settings that belong to this window, not to the backend: text size, motion, the last open tab.
// Saved in the window's own storage, so they survive a restart and need no backend call.

import { setQuiet } from "./poll.ts";

export type Motion = "system" | "on" | "off";
/** Dark is the app's own look; System follows the computer. */
export type Theme = "dark" | "light" | "system";
/** How long the logo stays over the app once it has loaded: 10 seconds, 1 second, or not at all. */
export type Intro = "long" | "short" | "off";
export type Cursor = "block" | "bar" | "underline";
/** What a terminal does when its program rings the bell: nothing, or a short flash of its border. */
export type Bell = "off" | "flash";
/** The size of all text outside the terminals. */
export type TextSize = "normal" | "large" | "larger";
/** Compact tightens the gaps between things. */
export type Density = "comfortable" | "compact";
type Prefs = {
  quiet: boolean;
  terminalFontSize: number;
  terminalScrollback: number;
  terminalCursor: Cursor;
  terminalCopyOnSelect: boolean;
  terminalBell: Bell;
  textSize: TextSize;
  density: Density;
  motion: Motion;
  theme: Theme;
  intro: Intro;
  rememberTab: boolean;
  lastTab: string;
  flags: Record<string, boolean>;
};

const KEY = "hippocampus.prefs";
export const FONT_MIN = 10;
export const FONT_MAX = 20;
export const SCROLLBACK_MIN = 500;
export const SCROLLBACK_MAX = 20000;
const DEFAULTS: Prefs = {
  quiet: false,
  terminalFontSize: 12,
  terminalScrollback: 5000,
  terminalCursor: "block",
  terminalCopyOnSelect: false,
  terminalBell: "off",
  textSize: "normal",
  density: "comfortable",
  motion: "system",
  theme: "dark",
  intro: "long",
  rememberTab: true,
  lastTab: "terminal",
  flags: {},
};

function clampScrollback(lines: number): number {
  return Math.min(SCROLLBACK_MAX, Math.max(SCROLLBACK_MIN, Math.round(lines)));
}

function read(): Prefs {
  try {
    const saved = JSON.parse(
      localStorage.getItem(KEY) ?? "{}",
    ) as Partial<Prefs>;
    const size = Number(saved.terminalFontSize);
    return {
      terminalFontSize: Number.isFinite(size)
        ? Math.min(FONT_MAX, Math.max(FONT_MIN, Math.round(size)))
        : DEFAULTS.terminalFontSize,
      terminalScrollback: Number.isFinite(Number(saved.terminalScrollback))
        ? clampScrollback(Number(saved.terminalScrollback))
        : DEFAULTS.terminalScrollback,
      terminalCursor:
        saved.terminalCursor === "bar" || saved.terminalCursor === "underline"
          ? saved.terminalCursor
          : "block",
      motion:
        saved.motion === "on" || saved.motion === "off"
          ? saved.motion
          : "system",
      theme:
        saved.theme === "light" || saved.theme === "system"
          ? saved.theme
          : "dark",
      intro:
        saved.intro === "short" || saved.intro === "off" ? saved.intro : "long",
      quiet: saved.quiet === true,
      terminalCopyOnSelect: saved.terminalCopyOnSelect === true,
      terminalBell: saved.terminalBell === "flash" ? "flash" : "off",
      textSize:
        saved.textSize === "large" || saved.textSize === "larger"
          ? saved.textSize
          : "normal",
      density: saved.density === "compact" ? "compact" : "comfortable",
      rememberTab: saved.rememberTab !== false,
      lastTab:
        typeof saved.lastTab === "string" ? saved.lastTab : DEFAULTS.lastTab,
      // Only true and false are kept, so a hand-edited value cannot switch a flag by accident.
      flags: Object.fromEntries(
        Object.entries(saved.flags ?? {}).filter(
          ([, on]) => typeof on === "boolean",
        ),
      ),
    };
  } catch {
    return { ...DEFAULTS, flags: {} };
  }
}

const state = $state<Prefs>(read());

function save(): void {
  try {
    localStorage.setItem(KEY, JSON.stringify(state));
  } catch {
    /* storage blocked: the setting still holds until the window closes */
  }
}

/** Puts the motion choice on the page, where global.css reads it. "system" follows the computer's setting. */
export function applyMotion(): void {
  // Quiet mode turns movement off whatever the Motion setting says.
  document.documentElement.dataset.motion = state.quiet ? "off" : state.motion;
  setQuiet(state.quiet);
}

/** Puts the text size and density on the page, where global.css reads them. */
export function applyLook(): void {
  document.documentElement.dataset.text = state.textSize;
  document.documentElement.dataset.density = state.density;
}

const systemLight =
  typeof matchMedia === "function"
    ? matchMedia("(prefers-color-scheme: light)")
    : null;

/** Puts the theme on the page, where tokens.css reads it, and tells the parts that draw with colours read in code. */
export function applyTheme(): void {
  const light =
    state.theme === "light" ||
    (state.theme === "system" && systemLight?.matches === true);
  const next = light ? "light" : "dark";
  if (document.documentElement.dataset.theme === next) return;
  document.documentElement.dataset.theme = next;
  // The graph and the terminals read their colours once; this tells them to read again.
  window.dispatchEvent(new CustomEvent("theme-changed", { detail: next }));
}
// With "System" chosen, the app follows the computer when it changes between light and dark.
systemLight?.addEventListener("change", applyTheme);

export const prefs = {
  get quiet(): boolean {
    return state.quiet;
  },
  set quiet(value: boolean) {
    state.quiet = value;
    applyMotion();
    save();
  },
  get terminalFontSize(): number {
    return state.terminalFontSize;
  },
  set terminalFontSize(size: number) {
    state.terminalFontSize = Math.min(
      FONT_MAX,
      Math.max(FONT_MIN, Math.round(size)),
    );
    save();
  },
  get terminalScrollback(): number {
    return state.terminalScrollback;
  },
  set terminalScrollback(lines: number) {
    state.terminalScrollback = clampScrollback(lines);
    save();
  },
  get terminalCursor(): Cursor {
    return state.terminalCursor;
  },
  set terminalCursor(value: Cursor) {
    state.terminalCursor = value;
    save();
  },
  get terminalCopyOnSelect(): boolean {
    return state.terminalCopyOnSelect;
  },
  set terminalCopyOnSelect(value: boolean) {
    state.terminalCopyOnSelect = value;
    save();
  },
  get terminalBell(): Bell {
    return state.terminalBell;
  },
  set terminalBell(value: Bell) {
    state.terminalBell = value;
    save();
  },
  get textSize(): TextSize {
    return state.textSize;
  },
  set textSize(value: TextSize) {
    state.textSize = value;
    applyLook();
    save();
  },
  get density(): Density {
    return state.density;
  },
  set density(value: Density) {
    state.density = value;
    applyLook();
    save();
  },
  get motion(): Motion {
    return state.motion;
  },
  set motion(value: Motion) {
    state.motion = value;
    applyMotion();
    save();
  },
  get theme(): Theme {
    return state.theme;
  },
  set theme(value: Theme) {
    state.theme = value;
    applyTheme();
    save();
  },
  get intro(): Intro {
    return state.intro;
  },
  set intro(value: Intro) {
    state.intro = value;
    save();
  },
  get rememberTab(): boolean {
    return state.rememberTab;
  },
  set rememberTab(value: boolean) {
    state.rememberTab = value;
    save();
  },
  get lastTab(): string {
    return state.lastTab;
  },
  set lastTab(value: string) {
    state.lastTab = value;
    save();
  },
  /** Feature flags switched by hand in Settings > Advanced; see flags.svelte.ts. */
  get flags(): Record<string, boolean> {
    return state.flags;
  },
  set flags(value: Record<string, boolean>) {
    state.flags = value;
    save();
  },
  reset(): void {
    // Appearance only: the feature flags keep their own switches.
    Object.assign(state, DEFAULTS, { flags: state.flags });
    applyMotion();
    applyTheme();
    applyLook();
    save();
  },
};
