// The agent card's pure model: accent colours, avatars and the avatar pick. No DOM, so it runs under node --test.

/** Each accent is a semantic colour token; the text on it is another token that passes AA. */
export const ACCENTS = {
  accent: { text: "accent-on" },
  think: { text: "bg-0" },
  confirm: { text: "bg-0" },
  danger: { text: "bg-0" },
} as const;

export type Accent = keyof typeof ACCENTS;

/** Pixel avatars in ui/assets/faces-new: avatar-XX (original) and card-face-XX (card set), drawn in the accent token. */
export const FACES = [
  "avatar-01.svg",
  "avatar-02.svg",
  "avatar-03.svg",
  "avatar-04.svg",
  "avatar-05.svg",
  "avatar-06.svg",
  "avatar-07.svg",
  "avatar-08.svg",
  "avatar-09.svg",
  "avatar-10.svg",
  "avatar-11.svg",
  "avatar-12.svg",
  "avatar-13.svg",
  "avatar-14.svg",
  "avatar-15.svg",
  "avatar-16.svg",
  "card-face-01.svg",
  "card-face-02.svg",
  "card-face-03.svg",
  "card-face-04.svg",
  "card-face-05.svg",
  "card-face-06.svg",
  "card-face-07.svg",
  "card-face-08.svg",
  "card-face-09.svg",
  "card-face-10.svg",
  "card-face-11.svg",
  "card-face-12.svg",
  "card-face-13.svg",
  "card-face-14.svg",
  "card-face-15.svg",
  "card-face-16.svg",
  "card-face-17.svg",
] as const;

/** The same name always gets the same face. */
export function faceFor(name: string): string {
  const sum = [...name].reduce(
    (total, ch) => total + (ch.codePointAt(0) ?? 0),
    0,
  );
  return FACES[sum % FACES.length] ?? FACES[0];
}
