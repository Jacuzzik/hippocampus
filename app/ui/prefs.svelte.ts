// Settings that belong to this window, not to the backend: text size, motion, the last open tab.
// Saved in the window's own storage, so they survive a restart and need no backend call.

export type Motion = "system" | "on" | "off";
/** How long the logo stays over the app once it has loaded: 10 seconds, 1 second, or not at all. */
export type Intro = "long" | "short" | "off";
type Prefs = {
  terminalFontSize: number;
  motion: Motion;
  intro: Intro;
  rememberTab: boolean;
  lastTab: string;
  flags: Record<string, boolean>;
};

const KEY = "hippocampus.prefs";
export const FONT_MIN = 10;
export const FONT_MAX = 20;
const DEFAULTS: Prefs = {
  terminalFontSize: 12,
  motion: "system",
  intro: "long",
  rememberTab: true,
  lastTab: "terminal",
  flags: {},
};

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
      motion:
        saved.motion === "on" || saved.motion === "off"
          ? saved.motion
          : "system",
      intro:
        saved.intro === "short" || saved.intro === "off" ? saved.intro : "long",
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
  document.documentElement.dataset.motion = state.motion;
}

export const prefs = {
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
  get motion(): Motion {
    return state.motion;
  },
  set motion(value: Motion) {
    state.motion = value;
    applyMotion();
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
    save();
  },
};
