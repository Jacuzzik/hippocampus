// How the spend meter writes token counts and what it says about a cap.

/** 950 -> "950", 12,340 -> "12.3k", 2,500,000 -> "2.5M". */
export function formatTokens(n: number): string {
  if (n < 1000) return String(Math.round(n));
  if (n < 1_000_000) return `${(n / 1000).toFixed(1).replace(/\.0$/, "")}k`;
  return `${(n / 1_000_000).toFixed(1).replace(/\.0$/, "")}M`;
}

export type Meter = { text: string; level: "ok" | "near" | "over" };

/** The app's tokens used today against its daily cap; a cap of 0 means no cap. */
export function meter(used: number, cap: number): Meter {
  if (!cap) return { text: `${formatTokens(used)} today`, level: "ok" };
  const level = used >= cap ? "over" : used >= cap * 0.8 ? "near" : "ok";
  return { text: `${formatTokens(used)} of ${formatTokens(cap)} today`, level };
}
