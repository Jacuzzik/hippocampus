// Subsequence match: every character of `query` must appear in `text`, in order.
// Consecutive hits and early hits score higher. Returns null when it does not match.
export function fuzzyScore(query: string, text: string): number | null {
  const q = query.trim().toLocaleLowerCase();
  const t = text.toLocaleLowerCase();
  let qi = 0;
  let score = 0;
  let last = -2;
  for (let i = 0; i < t.length && qi < q.length; i++) {
    if (t[i] !== q[qi]) continue;
    score += i === last + 1 ? 2 : 1;
    last = i;
    qi++;
  }
  return qi === q.length ? score : null;
}
