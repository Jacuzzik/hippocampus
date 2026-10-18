import logging

import pytest

from core.vault.parser import Link, Tag, normalize_target, parse_note


def link_keys(text: str) -> list[str]:
    return [link.target_key for link in parse_note(text, "note.md").links]


def tag_keys(text: str) -> list[tuple[str, str]]:
    return [(tag.tag_key, tag.source) for tag in parse_note(text, "note.md").tags]


def test_plain_link() -> None:
    (link,) = parse_note("See [[Other Note]].", "a.md").links
    assert link == Link("Other Note", "other note", None, None, False, 1)


def test_alias_heading_embed_and_line() -> None:
    text = "first\n\n![[Folder/Target.md#Part two|shown]]"
    (link,) = parse_note(text, "a.md").links
    assert link.target_key == "folder/target"
    assert link.heading == "Part two"
    assert link.alias == "shown"
    assert link.is_embed
    assert link.line == 3


def test_escaped_pipe_in_table() -> None:
    (link,) = parse_note("| [[Target\\|label]] |", "a.md").links
    assert (link.target_key, link.alias) == ("target", "label")


def test_same_note_heading_link_is_skipped() -> None:
    assert link_keys("[[#Intro]]") == []


def test_duplicate_links_are_kept() -> None:
    assert link_keys("[[A]] and [[a]]") == ["a", "a"]


@pytest.mark.parametrize(
    "text",
    [
        "```\n[[Hidden]] #hidden\n```",
        "~~~~python\n[[Hidden]] #hidden\n~~~~",
        "``` \n```not a close\n[[Hidden]] #hidden\n```",
        "`[[Hidden]] #hidden`",
        "``a ` [[Hidden]] #hidden``",
        "<!-- [[Hidden]]\n#hidden -->",
        "```\nunclosed fence runs to the end\n[[Hidden]] #hidden",
    ],
)
def test_code_and_comments_are_ignored(text: str) -> None:
    note = parse_note(text, "a.md")
    assert note.links == ()
    assert note.tags == ()


def test_text_after_code_block_still_counts() -> None:
    assert link_keys("```\n[[Hidden]]\n```\n[[Shown]]") == ["shown"]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("#tag", ["tag"]),
        ("a #Project/Alpha b", ["project/alpha"]),
        ("(#paren) [#bracket], #comma,", ["paren", "bracket", "comma"]),
        ("#snake_case and #kebab-case", ["snake_case", "kebab-case"]),
        ("#Café", ["café"]),
        ("#y2024 #2024 #1/2", ["y2024"]),
        ("# Heading\n## Sub", []),
        ("https://example.com/page#section", []),
        ("[link](#anchor) [ext](https://x.com/#frag)", []),
        ("issue#12 a#b", []),
        ("#trailing/", ["trailing"]),
    ],
)
def test_inline_tags(text: str, expected: list[str]) -> None:
    assert [key for key, _ in tag_keys(text)] == expected


def test_inline_tags_dedupe_case_insensitively_keeping_first_spelling() -> None:
    (tag,) = parse_note("#Idea #idea #IDEA", "a.md").tags
    assert tag == Tag("Idea", "idea", "inline")


@pytest.mark.parametrize(
    "frontmatter",
    [
        "tags: [alpha, '#Beta']",
        "tags:\n  - alpha\n  - Beta",
        "tags: alpha, Beta",
        "tags: alpha Beta",
        "tag: [alpha, beta]",
    ],
)
def test_frontmatter_tags(frontmatter: str) -> None:
    text = f"---\n{frontmatter}\n---\nbody"
    assert tag_keys(text) == [("alpha", "frontmatter"), ("beta", "frontmatter")]


def test_frontmatter_and_inline_tags_are_both_kept() -> None:
    text = "---\ntags: [shared]\n---\n#shared #inline"
    assert tag_keys(text) == [
        ("shared", "inline"),
        ("inline", "inline"),
        ("shared", "frontmatter"),
    ]


def test_non_string_frontmatter_tags_are_skipped() -> None:
    assert tag_keys("---\ntags: [2024, ok, null, {a: b}]\n---\n") == [("ok", "frontmatter")]


def test_frontmatter_text_is_not_parsed_as_body() -> None:
    text = "---\nsummary: '[[NotALink]] #nottag'\n---\nbody"
    note = parse_note(text, "a.md")
    assert note.links == ()
    assert note.tags == ()
    assert note.frontmatter == {"summary": "[[NotALink]] #nottag"}


def test_line_numbers_count_frontmatter_lines() -> None:
    (link,) = parse_note("---\na: 1\n---\n[[X]]", "a.md").links
    assert link.line == 4


def test_invalid_yaml_is_logged_and_body_still_indexed(caplog: pytest.LogCaptureFixture) -> None:
    text = "---\ntags: [unclosed\n---\n[[Body]] #ok"
    with caplog.at_level(logging.WARNING, logger="hippocampus.core.vault"):
        note = parse_note(text, "dir/bad.md")
    assert "dir/bad.md" in caplog.text
    assert note.frontmatter == {}
    assert [link.target_key for link in note.links] == ["body"]
    assert [tag.tag_key for tag in note.tags] == ["ok"]


def test_non_mapping_frontmatter_is_logged(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.WARNING, logger="hippocampus.core.vault"):
        note = parse_note("---\n- a\n- b\n---\n", "list.md")
    assert note.frontmatter == {}
    assert "list.md" in caplog.text


def test_empty_frontmatter() -> None:
    note = parse_note("---\n---\n# Title", "a.md")
    assert note.frontmatter == {}
    assert note.title == "Title"


def test_title_prefers_frontmatter_then_h1_then_file_name() -> None:
    assert parse_note("---\ntitle: From FM\n---\n# H1", "a.md").title == "From FM"
    assert parse_note("intro\n# The H1 ##\n# Second", "a.md").title == "The H1"
    assert parse_note("```\n# in code\n```\nno heading", "dir/File Name.md").title == "File Name"


def test_crlf_and_bom() -> None:
    note = parse_note("﻿---\r\ntags: [a]\r\n---\r\n[[B]]\r\n", "a.md")
    assert [t.tag_key for t in note.tags] == ["a"]
    assert note.links[0].line == 4


@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ("Note", "note"),
        ("  Folder/Note.md ", "folder/note"),
        ("./Folder\\Note", "folder/note"),
        ("/Root", "root"),
        ("Note.MD", "note"),
    ],
)
def test_normalize_target(raw: str, key: str) -> None:
    assert normalize_target(raw) == key
