"""Requirement 1.3, 1.4, 1.5 — a publish is rejected cleanly, or not at all."""

import pytest

from skills_catalog.repository import SqliteRepository

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


def test_rejected_publish_is_atomic(service, tmp_path):
    """1.5 — a rejected publish leaves no trace: no skill, version, file or index row."""
    service.publish({"SKILL.md": MANIFEST, "../escape.md": "x"})

    repository: SqliteRepository = service.repository
    with repository._connect() as conn:
        for table in ("skills", "versions", "version_files", "skills_fts"):
            count = conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
            assert count == 0, f"{table} should be empty after a rejected publish"
