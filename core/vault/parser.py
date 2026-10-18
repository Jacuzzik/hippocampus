"""Parse one note's text into a title, wiki links and tags.

Pure functions, no file access. Code, HTML comments, link destinations and
frontmatter are masked with spaces before matching, so they never yield links
or tags but line numbers still match the file.
"""

import bisect
import logging
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any, Literal

import yaml

logger = logging.getLogger("hippocampus.core.vault")

TagSource = Literal["inline", "frontmatter"]

_FRONTMATTER = re.compile(r"\A---[ \t]*\n(.*?\n)?(?:---|\.\.\.)[ \t]*(?:\n|\Z)", re.DOTALL)
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
_INLINE_CODE = re.compile(r"(`+)(?!`).+?(?<!`)\1(?!`)")
_HTML_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_LINK_DESTINATION = re.compile(r"\]\([^)\n]*\)")
_WIKILINK = re.compile(r"(!)?\[\[([^\[\]\n]+?)\]\]")
_TAG_BODY = r"[\w/-]+"
_INLINE_TAG = re.compile(r"(?<![^\s(\[{,;:!?\"'])#(" + _TAG_BODY + ")")
_VALID_TAG = re.compile(_TAG_BODY)
_H1 = re.compile(r"^ {0,3}#[ \t]+(.+?)(?:[ \t]+#+)?[ \t]*$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class Link:
    target_raw: str
    target_key: str
    alias: str | None
    heading: str | None
    is_embed: bool
    line: int


@dataclass(frozen=True, slots=True)
class Tag:
    tag: str
    tag_key: str
    source: TagSource


@dataclass(frozen=True, slots=True)
class ParsedNote:
    title: str
    links: tuple[Link, ...]
    tags: tuple[Tag, ...]
    frontmatter: dict[str, Any] = field(default_factory=dict)


def normalize_target(target: str) -> str:
    """Key used to match a link target against note paths and names."""
    key = target.strip().replace("\\", "/").lstrip("/")
    while key.startswith("./"):
        key = key[2:]
    if key.lower().endswith(".md"):
        key = key[:-3]
    return key.casefold()


def parse_note(text: str, path: str) -> ParsedNote:
    """Parse a note. `path` is the vault-relative path, used for the title fallback and logs."""
    text = text.removeprefix("﻿").replace("\r\n", "\n").replace("\r", "\n")
    frontmatter, masked = _split_frontmatter(text, path)
    masked = _mask_code_and_comments(masked)

    title = _title(frontmatter, masked, path)
    links = tuple(_links(masked))
    tags = _dedupe(
        [*_inline_tags(masked), *_frontmatter_tags(frontmatter, path)],
    )
    return ParsedNote(title=title, links=links, tags=tags, frontmatter=frontmatter)


def _blank(chunk: str) -> str:
    return re.sub(r"[^\n]", " ", chunk)


def _split_frontmatter(text: str, path: str) -> tuple[dict[str, Any], str]:
    match = _FRONTMATTER.match(text)
    if match is None:
        return {}, text
    masked = _blank(match.group(0)) + text[match.end() :]
    try:
        data = yaml.safe_load(match.group(1) or "")
    except yaml.YAMLError as exc:
        logger.warning("Ignoring invalid frontmatter in %s: %s", path, exc)
        return {}, masked
    if data is None:
        return {}, masked
    if not isinstance(data, dict):
        logger.warning("Ignoring frontmatter in %s: expected a mapping, got %s", path, type(data))
        return {}, masked
    return {str(k): v for k, v in data.items()}, masked


def _mask_code_and_comments(text: str) -> str:
    lines = text.split("\n")
    fence: str | None = None
    for i, line in enumerate(lines):
        match = _FENCE.match(line)
        if fence is None:
            if match:
                fence = match.group(1)
                lines[i] = _blank(line)
        else:
            closing = match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence)
            if closing and not line[match.end() :].strip():
                fence = None
            lines[i] = _blank(line)
    text = "\n".join(lines)
    for pattern in (_HTML_COMMENT, _INLINE_CODE, _LINK_DESTINATION):
        text = pattern.sub(lambda m: _blank(m.group(0)), text)
    return text


def _title(frontmatter: dict[str, Any], masked: str, path: str) -> str:
    fm_title = frontmatter.get("title")
    if isinstance(fm_title, str) and fm_title.strip():
        return fm_title.strip()
    match = _H1.search(masked)
    if match:
        return match.group(1).strip()
    return PurePosixPath(path).stem


def _links(masked: str) -> list[Link]:
    newlines = [i for i, ch in enumerate(masked) if ch == "\n"]
    links = []
    for match in _WIKILINK.finditer(masked):
        inner = match.group(2).replace("\\|", "|")
        target, _, alias = inner.partition("|")
        name, _, heading = target.partition("#")
        if not name.strip():
            continue  # [[#Heading]] points inside the same note
        links.append(
            Link(
                target_raw=target.strip(),
                target_key=normalize_target(name),
                alias=alias.strip() or None,
                heading=heading.strip() or None,
                is_embed=match.group(1) is not None,
                line=bisect.bisect_left(newlines, match.start()) + 1,
            )
        )
    return links


def _make_tag(raw: str, source: TagSource) -> Tag | None:
    body = raw.strip().removeprefix("#").rstrip("/")
    if not body or not _VALID_TAG.fullmatch(body):
        return None
    if body.replace("/", "").isdigit():
        return None  # all-number tags are not tags, as in Obsidian
    return Tag(tag=body, tag_key=body.casefold(), source=source)


def _inline_tags(masked: str) -> list[Tag]:
    tags = (_make_tag(m.group(1), "inline") for m in _INLINE_TAG.finditer(masked))
    return [t for t in tags if t is not None]


def _frontmatter_tags(frontmatter: dict[str, Any], path: str) -> list[Tag]:
    value = frontmatter.get("tags", frontmatter.get("tag"))
    if value is None:
        return []
    if isinstance(value, str):
        items: list[Any] = re.split(r"[,\s]+", value)
    elif isinstance(value, list):
        items = value
    else:
        logger.warning("Ignoring frontmatter tags in %s: expected a list or string", path)
        return []
    tags = []
    for item in items:
        tag = _make_tag(item, "frontmatter") if isinstance(item, str) else None
        if tag is not None:
            tags.append(tag)
        elif item != "":
            logger.debug("Skipping invalid frontmatter tag %r in %s", item, path)
    return tags


def _dedupe(tags: list[Tag]) -> tuple[Tag, ...]:
    seen: set[tuple[str, str]] = set()
    unique = []
    for tag in tags:
        key = (tag.tag_key, tag.source)
        if key not in seen:
            seen.add(key)
            unique.append(tag)
    return tuple(unique)
