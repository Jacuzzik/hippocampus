// Reads a colour token from the page, for code that cannot use var(): canvas drawing and the terminal.
// Colours live in design/tokens.json only; nothing here carries its own copy.

/** The value of --color-<name>, for example cssToken("md-text"). Empty if the token does not exist. */
export function cssToken(name: string): string {
  return getComputedStyle(document.documentElement)
    .getPropertyValue(`--color-${name}`)
    .trim();
}

/** The font stack in --font-<name>, for example fontToken("mono"). Falls back to plain monospace. */
export function fontToken(name: string): string {
  return (
    getComputedStyle(document.documentElement)
      .getPropertyValue(`--font-${name}`)
      .trim() || "monospace"
  );
}
