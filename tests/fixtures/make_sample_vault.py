"""Generate a deterministic sample vault, plus a manifest of what the index should hold.

Used by the tests (always into tmp_path) and by hand:

    uv run python tests/fixtures/make_sample_vault.py brains/sample [--count 200] [--seed 42]

Standard library only, so it never depends on the code it checks.
"""

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Any

FOLDERS = [
    "",
    "projects",
    "projects/alpha",
    "areas",
    "areas/health",
    "resources",
    "journal/2026",
    "archive",
]
WORDS = [
    "memory", "graph", "garden", "signal", "river", "lantern", "atlas", "orbit",
    "harbor", "meadow", "compass", "ember", "thread", "summit", "canvas", "echo",
]  # fmt: skip
TAGS = ["idea", "todo", "reading", "project/alpha", "project/beta", "health", "Review", "draft"]
ORPHAN_SHARE = 0.05
DANGLING_SHARE = 0.10
MANIFEST = "manifest.json"


def _name_key(name: str) -> str:
    return name.casefold()


def generate(dest: Path, count: int = 200, seed: int = 42) -> dict[str, Any]:
    """Write `count` notes under `dest` and return the manifest (also saved as manifest.json)."""
    if count < 20:
        raise ValueError("count must be at least 20")
    rng = random.Random(seed)

    # Plan every note first, so links can point anywhere.
    paths: list[str] = []
    for i in range(count - 2):
        folder = FOLDERS[i % len(FOLDERS)]
        name = f"Note {i:04d} {WORDS[i % len(WORDS)]}"
        paths.append(f"{folder}/{name}.md" if folder else f"{name}.md")
    # Two notes with the same name; [[Index]] resolves to the shorter path.
    paths += ["projects/Index.md", "archive/Index.md"]
    by_name = {_name_key(Path(p).stem): p for p in paths if Path(p).stem != "Index"}
    by_name["index"] = "archive/Index.md"

    orphans = set(paths[count - 2 - int(count * ORPHAN_SHARE) : count - 2])
    linkable = [p for p in paths if p not in orphans]

    notes: dict[str, Any] = {}
    dangling_id = 0
    for i, path in enumerate(paths):
        stem = Path(path).stem
        lines: list[str] = []
        tags: dict[tuple[str, str], str] = {}
        links: list[list[str | None]] = []

        fm_tags = rng.sample(TAGS, rng.randint(1, 2)) if i % 3 == 0 else []
        use_fm_title = i % 5 == 0
        title = f"{stem} (titled)" if use_fm_title else stem
        if fm_tags or use_fm_title:
            lines.append("---")
            if use_fm_title:
                lines.append(f"title: {title}")
            if fm_tags:
                lines.append("tags: [" + ", ".join(fm_tags) + "]")
            lines.append("---")
            for tag in fm_tags:
                tags.setdefault((tag.casefold(), "frontmatter"), tag)
        if not use_fm_title:
            lines.append(f"# {title}")
        lines.append("")

        inline = rng.sample(TAGS, rng.randint(0, 2))
        lines.append("Some text about " + " ".join(f"#{t}" for t in inline) + ".")
        for tag in inline:
            tags.setdefault((tag.casefold(), "inline"), tag)

        if path not in orphans:
            for _ in range(rng.randint(1, 5)):
                if rng.random() < DANGLING_SHARE:
                    raw = f"Missing Topic {dangling_id}"
                    dangling_id += 1
                    lines.append(f"See [[{raw}]].")
                    links.append([raw, None])
                    continue
                target = rng.choice([p for p in linkable if p != path])
                target_stem = Path(target).stem
                form = rng.choice(["plain", "alias", "heading", "embed", "path"])
                if target_stem == "Index":
                    form, target = "plain", by_name["index"]
                raw = target_stem
                if form == "alias":
                    lines.append(f"Related: [[{target_stem}|see this]].")
                elif form == "heading":
                    raw = f"{target_stem}#Details"
                    lines.append(f"Details in [[{raw}]].")
                elif form == "embed":
                    lines.append(f"![[{target_stem}]]")
                elif form == "path":
                    raw = target.removesuffix(".md")
                    lines.append(f"Path link [[{raw}]].")
                else:
                    lines.append(f"See [[{target_stem}]].")
                links.append([raw, target])

        if i % 7 == 0:
            lines += ["", "```", "[[Not A Link]] #not-a-tag", "```", "`[[Inline Code]]`"]
        if i % 11 == 0:
            lines.append("Heading-style text: # not a tag, url https://x.com/page#frag")

        file = dest / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        notes[path] = {
            "title": title,
            "links": links,
            "tags": sorted([key, source] for key, source in tags),
        }

    manifest = {
        "count": count,
        "seed": seed,
        "notes": notes,
        "totals": {
            "notes": len(notes),
            "links": sum(len(n["links"]) for n in notes.values()),
            "dangling_links": sum(1 for n in notes.values() for _, t in n["links"] if t is None),
            "tags": sum(len(n["tags"]) for n in notes.values()),
            "distinct_tags": len({key for n in notes.values() for key, _ in n["tags"]}),
        },
        "orphans": sorted(orphans),
    }
    (dest / MANIFEST).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("dest", type=Path, help="folder to create; must be empty or missing")
    parser.add_argument("--count", type=int, default=200)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)
    if args.dest.exists() and any(args.dest.iterdir()):
        print(f"{args.dest} is not empty; remove it or pick another folder", file=sys.stderr)
        return 1
    manifest = generate(args.dest, args.count, args.seed)
    print(f"Wrote {manifest['totals']['notes']} notes to {args.dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
