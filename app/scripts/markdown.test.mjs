// Tests for ui/graph/markdown.ts. Node 24 strips the types when it imports the .ts file.
import assert from "node:assert/strict";
import { test } from "node:test";
import { parseNote } from "../ui/graph/markdown.ts";

test("headings, lists, code and paragraphs become blocks", () => {
  const blocks = parseNote(
    "# Title\n\nSome *words*\nand more.\n\n- one\n- two\n\n1. first\n\n```\nx < 1\n```\n",
  );
  assert.deepEqual(
    blocks.map((b) => b.kind),
    ["heading", "paragraph", "list", "list", "code"],
  );
  assert.equal(blocks[0].level, 1);
  assert.deepEqual(blocks[1].children, [
    { kind: "text", text: "Some " },
    { kind: "em", text: "words" },
    { kind: "text", text: " and more." },
  ]);
  assert.equal(blocks[2].items.length, 2);
  assert.equal(blocks[3].ordered, true);
  assert.equal(blocks[4].text, "x < 1");
});

test("wikilinks keep their target and label", () => {
  const [para] = parseNote("See [[Beta]] and [[gamma.md|the last]].");
  assert.deepEqual(
    para.children.filter((p) => p.kind === "wiki"),
    [
      { kind: "wiki", target: "Beta", text: "Beta" },
      { kind: "wiki", target: "gamma.md", text: "the last" },
    ],
  );
});

test("only http and https links become links; the rest stays text", () => {
  const [para] = parseNote(
    "[ok](https://a.test) and [bad](javascript:alert(1))",
  );
  assert.deepEqual(para.children[0], {
    kind: "link",
    href: "https://a.test",
    text: "ok",
  });
  assert.equal(
    para.children.some(
      (p) => p.kind === "link" && p.href.startsWith("javascript"),
    ),
    false,
  );
});

test("markup in a note is plain text, never HTML", () => {
  const [para] = parseNote("<img src=x onerror=alert(1)> `<b>`");
  assert.equal(para.children[0].text, "<img src=x onerror=alert(1)> ");
  assert.deepEqual(para.children[1], { kind: "code", text: "<b>" });
});
