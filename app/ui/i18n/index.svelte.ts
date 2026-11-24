// 7.30: languages. English text in the components is the key; a catalogue gives the same phrase in another language.
// A phrase with no entry shows in English, so a missing translation is never blank. Direction follows the language.
import { AR } from "./catalog.ar.ts";
import { ZH } from "./catalog.zh.ts";

export type Language = "en" | "zh-Hans" | "ar";
export const LANGUAGES: { id: Language; label: string; dir: "ltr" | "rtl" }[] =
  [
    { id: "en", label: "English", dir: "ltr" },
    { id: "zh-Hans", label: "简体中文", dir: "ltr" },
    { id: "ar", label: "العربية", dir: "rtl" },
  ];
const KEY = "hippocampus.language";
const CATALOGS: Record<Language, Record<string, string>> = {
  en: {},
  "zh-Hans": ZH,
  ar: AR,
};

function read(): Language {
  try {
    const saved = localStorage.getItem(KEY);
    return LANGUAGES.some((l) => l.id === saved) ? (saved as Language) : "en";
  } catch {
    return "en";
  }
}

export const language = $state<{ id: Language }>({ id: read() });

/** The phrase in the chosen language, or the English phrase when there is no entry. */
export function t(text: string): string {
  return CATALOGS[language.id][text] ?? text;
}

/** A phrase with {name} holes, filled in: tf("Step {n} of {m}", { n: 1, m: 5 }). */
export function tf(
  text: string,
  values: Record<string, string | number>,
): string {
  return t(text).replace(/\{(\w+)\}/g, (hole, name: string) =>
    name in values ? String(values[name]) : hole,
  );
}

/** Puts the language and its direction on the page, where the style sheet reads them. */
export function applyLanguage(): void {
  const found = LANGUAGES.find((l) => l.id === language.id) ?? {
    id: "en",
    dir: "ltr",
  };
  document.documentElement.lang = found.id;
  document.documentElement.dir = found.dir;
}

export function setLanguage(id: Language): void {
  language.id = id;
  try {
    localStorage.setItem(KEY, id);
  } catch {
    /* storage blocked: the choice holds until the window closes */
  }
  applyLanguage();
}
