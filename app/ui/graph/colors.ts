// Reads design tokens (CSS custom properties from tokens.css) as RGBA 0 to 1, so no colour is hardcoded here.
import type { Rgba } from "./renderer";

const ctx = document
  .createElement("canvas")
  .getContext("2d", { willReadFrequently: true });

export function token(name: string): Rgba {
  if (!ctx)
    throw new Error("Canvas 2D is not available; cannot read design tokens");
  const value = getComputedStyle(document.documentElement)
    .getPropertyValue(`--color-${name}`)
    .trim();
  if (!value)
    throw new Error(
      `Design token --color-${name} is missing; run npm run tokens`,
    );
  ctx.clearRect(0, 0, 1, 1);
  ctx.fillStyle = value;
  ctx.fillRect(0, 0, 1, 1);
  const [r = 0, g = 0, b = 0, a = 0] = ctx.getImageData(0, 0, 1, 1).data;
  return [r / 255, g / 255, b / 255, a / 255];
}
