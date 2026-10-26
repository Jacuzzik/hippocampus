// A small Markdown reader for the note drawer. It builds plain data, never HTML, so the
// Svelte template escapes every piece and a note cannot inject markup.

export type Inline =
  | { kind: "text"; text: string }
  | { kind: "code"; text: string }
  | { kind: "strong"; text: string }
  | { kind: "em"; text: string }
  | { kind: "link"; href: string; text: string }
  | { kind: "wiki"; target: string; text: string };

export type Block =
  | { kind: "heading"; level: number; children: Inline[] }
  | { kind: "paragraph"; children: Inline[] }
  | { kind: "list"; ordered: boolean; items: Inline[][] }
  | { kind: "code"; text: string };

const LIST_ITEM = /^\s*(?:([-*])|(\d+)\.)\s+(.*)$/;
const HEADING = /^(#{1,6})\s+(.*)$/;
const FENCE = /^\s*```/;
// One pass over the line: code, [[wikilink]] (with an optional |label), [text](url), **bold**, *em*.
const INLINE =
  /`([^`]+)`|\[\[([^\]|]+)(?:\|([^\]]+))?\]\]|\[([^\]]+)\]\(([^)\s]+)\)|\*\*([^*]+)\*\*|\*([^*]+)\*/g;

export function parseInline(line: string): Inline[] {
  const out: Inline[] = [];
  let last = 0;
  for (const m of line.matchAll(INLINE)) {
    if (m.index > last)
      out.push({ kind: "text", text: line.slice(last, m.index) });
    last = m.index + m[0].length;
    if (m[1] !== undefined) out.push({ kind: "code", text: m[1] });
    else if (m[2] !== undefined)
      out.push({
        kind: "wiki",
        target: m[2].trim(),
        text: (m[3] ?? m[2]).trim(),
      });
    else if (m[4] !== undefined && /^https?:\/\//i.test(m[5] ?? ""))
      out.push({ kind: "link", href: m[5] ?? "", text: m[4] });
    else if (m[4] !== undefined) out.push({ kind: "text", text: m[0] });
    else if (m[6] !== undefined) out.push({ kind: "strong", text: m[6] ?? "" });
    else out.push({ kind: "em", text: m[7] ?? "" });
  }
  if (last < line.length) out.push({ kind: "text", text: line.slice(last) });
  return out;
}

export function parseNote(markdown: string): Block[] {
  const blocks: Block[] = [];
  const lines = markdown.replace(/\r\n?/g, "\n").split("\n");
  let paragraph: string[] = [];
  let code: string[] | null = null;
  let list: Extract<Block, { kind: "list" }> | null = null;

  const flush = () => {
    if (paragraph.length)
      blocks.push({
        kind: "paragraph",
        children: parseInline(paragraph.join(" ")),
      });
    paragraph = [];
    list = null;
  };

  for (const line of lines) {
    if (code !== null) {
      if (FENCE.test(line)) {
        blocks.push({ kind: "code", text: code.join("\n") });
        code = null;
      } else code.push(line);
      continue;
    }
    if (FENCE.test(line)) {
      flush();
      code = [];
      continue;
    }
    const item = LIST_ITEM.exec(line);
    if (item) {
      if (paragraph.length) flush();
      const ordered = item[2] !== undefined;
      if (!list || list.ordered !== ordered) {
        list = { kind: "list", ordered, items: [] };
        blocks.push(list);
      }
      list.items.push(parseInline(item[3] ?? ""));
      continue;
    }
    const heading = HEADING.exec(line);
    if (heading) {
      flush();
      blocks.push({
        kind: "heading",
        level: (heading[1] ?? "").length,
        children: parseInline(heading[2] ?? ""),
      });
    } else if (line.trim() === "") flush();
    else {
      list = null;
      paragraph.push(line.trim());
    }
  }
  if (code !== null) blocks.push({ kind: "code", text: code.join("\n") });
  flush();
  return blocks;
}
