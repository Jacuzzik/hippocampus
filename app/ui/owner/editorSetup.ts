// 7.18: CodeMirror 6 for the built-in code editor. Colours come from the app's design tokens (CSS variables).
import { basicSetup } from "codemirror";
import { EditorView, keymap } from "@codemirror/view";
import { EditorState, type Extension } from "@codemirror/state";
import { javascript } from "@codemirror/lang-javascript";
import { json } from "@codemirror/lang-json";
import { markdown } from "@codemirror/lang-markdown";
import { python } from "@codemirror/lang-python";

const theme = EditorView.theme({
  "&": {
    height: "100%",
    color: "var(--color-text)",
    backgroundColor: "var(--color-bg-0)",
    fontSize: "var(--font-size-sm)",
  },
  ".cm-scroller": { fontFamily: "var(--font-mono)" },
  ".cm-gutters": {
    backgroundColor: "var(--color-bg-1)",
    color: "var(--color-text-subtle)",
    border: "none",
  },
  ".cm-cursor": { borderLeftColor: "var(--color-text)" },
  "&.cm-focused": { outline: "1px solid var(--color-focus-ring)" },
  ".cm-activeLine, .cm-activeLineGutter": {
    backgroundColor: "var(--color-bg-1)",
  },
});

/** The language for a file name, or nothing for a plain-text file. */
export function languageFor(path: string): Extension[] {
  const ext = path.slice(path.lastIndexOf(".") + 1).toLowerCase();
  if (["js", "mjs", "cjs", "jsx"].includes(ext)) return [javascript()];
  if (["ts", "tsx"].includes(ext))
    return [javascript({ typescript: true, jsx: ext === "tsx" })];
  if (ext === "json") return [json()];
  if (["md", "markdown"].includes(ext)) return [markdown()];
  if (ext === "py") return [python()];
  return [];
}

/** A fresh editor state for a file: its text, its language, and a hook that says when the text changes. */
export function makeState(
  path: string,
  text: string,
  onchange: (text: string) => void,
  onsave: () => void,
): EditorState {
  return EditorState.create({
    doc: text,
    extensions: [
      basicSetup,
      theme,
      ...languageFor(path),
      keymap.of([
        {
          key: "Mod-s",
          preventDefault: true,
          run: () => {
            onsave();
            return true;
          },
        },
      ]),
      EditorView.updateListener.of((update) => {
        if (update.docChanged) onchange(update.state.doc.toString());
      }),
    ],
  });
}

export { EditorView };
