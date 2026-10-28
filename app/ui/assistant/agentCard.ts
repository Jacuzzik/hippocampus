// The agent card's pure model: accent colours, faces and the face pick. No DOM, so it runs under node --test.

/** Each accent is a semantic colour token; the text on it is another token that passes AA. */
export const ACCENTS = {
  accent: { text: "accent-on" },
  think: { text: "bg-0" },
  confirm: { text: "bg-0" },
  danger: { text: "bg-0" },
} as const;

export type Accent = keyof typeof ACCENTS;

/** The approved female faces in ui/assets/faces. Approved by Thalha on 2026-10-26; the numbers are the originals. */
export const FACES = [
  "face-01.png",
  "face-03.png",
  "face-04.png",
  "face-05.png",
  "face-06.png",
  "face-08.png",
  "face-09.png",
  "face-10.png",
] as const;

/** The same name always gets the same face. */
export function faceFor(name: string): string {
  const sum = [...name].reduce(
    (total, ch) => total + (ch.codePointAt(0) ?? 0),
    0,
  );
  return FACES[sum % FACES.length] ?? FACES[0];
}
