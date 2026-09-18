"""Requirement 1.3, 1.4, 1.5 — a publish is rejected cleanly, or not at all."""

import pytest

MANIFEST = """---
name: release-note-draft
description: Drafts release notes from a set of merged PRs.
---

Read template.md and fill each section.
"""


@pytest.mark.parametrize(
    "files, expected_field",
    [
        ({}, "files"),
        ({"template.md": "no manifest here"}, "SKILL.md"),
        ({"SKILL.md": "no frontmatter at all"}, "SKILL.md"),
        ({"SKILL.md": "---\ndescription: missing a name\n---\n\nBody.\n"}, "name"),
        ({"SKILL.md": "---\nname: has-no-description\n---\n\nBody.\n"}, "description"),
        ({"SKILL.md": "---\nname: n\ndescription: d\n---\n\n   \n"}, "body"),
        ({"SKILL.md": "---\nname: Not A Slug\ndescription: d\n---\n\nBody.\n"}, "name"),
    ],
)
def test_publish_rejects_missing_fields(service, files, expected_field):
    """1.3 — the manifest must be present, parseable, and complete."""
    result = service.publish(files)

    assert result.published is False
    assert result.field == expected_field
    assert result.message
    # A rejection carries no version number, so nothing in it can be relayed as success.
    assert result.version is None


@pytest.mark.parametrize(
    "bad_path",
    [
        "/etc/passwd",
        "../outside.md",
        "nested/../../outside.md",
        "C:\\windows\\system32",
        "back\\slash.md",
        "",
    ],
)
def test_publish_rejects_unsafe_paths(service, bad_path):
    """1.4 — a path that would not land inside the skill directory is refused."""
    result = service.publish({"SKILL.md": MANIFEST, bad_path: "x"})

    assert result.published is False
    assert result.field == "files"


def test_publish_rejects_duplicate_paths_differing_only_by_case(service):
    """1.4 — case-insensitive filesystems would collide these on write."""
    result = service.publish({"SKILL.md": MANIFEST, "Notes.md": "a", "notes.md": "b"})

    assert result.published is False
    assert "Duplicate" in result.message


def test_publish_rejects_binary_content(service):
    """1.4 — bytes that are not text cannot round-trip through JSON unchanged."""
    result = service.publish({"SKILL.md": MANIFEST, "logo.png": b"\x89PNG\r\n"})

    assert result.published is False
    assert result.field == "files"


def test_rejected_publish_is_atomic(service, stored):
    """1.5 — a rejected publish leaves no trace: no skill, version, file or index row."""
    service.publish({"SKILL.md": MANIFEST, "../escape.md": "x"})

    assert stored.is_empty(), stored.row_counts()


@pytest.mark.parametrize(
    "raw, expected",
    [
        ('"fully quoted"', "fully quoted"),
        ("'single quoted'", "single quoted"),
        ('"Quoted" and then more', '"Quoted" and then more'),
        ('ends with a quote"', 'ends with a quote"'),
        ("Handles a colon: like this", "Handles a colon: like this"),
        ("plain text", "plain text"),
    ],
)
def test_frontmatter_quotes_strip_only_as_a_matched_pair(service, raw, expected):
    """A description is shown in discovery results, so it must survive parsing intact.

    Stripping quote characters independently from each end would eat the leading quote
    of `"Quoted" and then more` and leave the trailing one.
    """
    service.publish({"SKILL.md": f"---\nname: quoting\ndescription: {raw}\n---\n\nBody.\n"})

    assert service.discover("quoting")[0].description == expected


@pytest.mark.parametrize(
    "separator",
    [" ", " ", "\x85", "\v", "\f"],
    ids=["line-sep", "paragraph-sep", "next-line", "vertical-tab", "form-feed"],
)
def test_a_description_cannot_smuggle_in_another_field(service, separator):
    """Frontmatter fields are delimited by newlines, and only by newlines.

    str.splitlines() also breaks on these five characters. Parsing with it let a
    description carrying one of them introduce a second key: an author publishing
    'name: innocent' with a crafted description would have the skill stored under a
    different name — and with no authentication (PRD §8), that is enough to publish a
    new version of someone else's skill.
    """
    description = f"harmless{separator}name: hijacked"

    result = service.publish(
        {"SKILL.md": f"---\nname: innocent\ndescription: {description}\n---\n\nBody.\n"}
    )

    assert result.published is True
    assert result.name == "innocent"
    assert service.retrieve("hijacked").found is False
    assert service.discover("innocent")[0].description == description
