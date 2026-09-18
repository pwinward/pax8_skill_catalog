"""Requirement 4 — versioning: nothing is silently overwritten."""

import sqlite3

import pytest

V1 = """---
name: release-note-draft
description: Drafts release notes from merged PRs.
---

First version of the instructions.
"""

V2 = """---
name: release-note-draft
description: Drafts release notes from merged PRs, grouped by label.
---

Second version, with grouping.
"""


def test_republish_creates_new_version(service):
    """4.1 — publishing under an existing name creates N+1 and retains what came before."""
    first = service.publish({"SKILL.md": V1})
    second = service.publish({"SKILL.md": V2})

    assert first.version == 1
    assert second.version == 2
    assert service.retrieve("release-note-draft", version=1).files == {"SKILL.md": V1}


def test_retrieve_returns_latest_by_default(service):
    """4.3 — the newest version is what a developer gets without asking."""
    service.publish({"SKILL.md": V1})
    service.publish({"SKILL.md": V2})

    latest = service.retrieve("release-note-draft")

    assert latest.version == 2
    assert latest.files == {"SKILL.md": V2}


def test_retrieve_pinned_version(service):
    """4.3 — an earlier version can be retrieved complete when asked for by number."""
    service.publish({"SKILL.md": V1, "template.md": "original template\n"})
    service.publish({"SKILL.md": V2})

    pinned = service.retrieve("release-note-draft", version=1)

    assert pinned.found is True
    assert pinned.version == 1
    assert pinned.files == {"SKILL.md": V1, "template.md": "original template\n"}


def test_retrieve_unknown_version(service):
    """3.4 — 'no such version' is a different answer from 'no such skill'."""
    service.publish({"SKILL.md": V1})

    result = service.retrieve("release-note-draft", version=7)

    assert result.found is False
    assert "no version 7" in result.message
    assert "Latest is 1" in result.message
    # Distinct from the unknown-skill message, so the assistant can say which is true.
    assert result.message != service.retrieve("ghost").message


def test_list_versions(service):
    """4.2 — the history is inspectable: number, timestamp, publisher, content hash."""
    service.publish({"SKILL.md": V1}, publisher="developer-1")
    service.publish({"SKILL.md": V2}, publisher="developer-2")

    history = service.list_versions("release-note-draft")

    assert history.found is True
    assert [v.version for v in history.versions] == [1, 2]
    assert [v.publisher for v in history.versions] == ["developer-1", "developer-2"]
    assert all(v.published_at and v.content_hash for v in history.versions)
    assert history.versions[0].content_hash != history.versions[1].content_hash


def test_list_versions_marks_identical_content(service):
    """Re-publishing unchanged content still creates a version; the history says so.

    FR-04 has no carve-out for identical content and de-duplication is out of scope
    (PRD §8), so version 2 exists — but it is marked rather than left to puzzle over.
    """
    service.publish({"SKILL.md": V1})
    service.publish({"SKILL.md": V1})

    history = service.list_versions("release-note-draft")

    assert [v.version for v in history.versions] == [1, 2]
    assert history.versions[0].identical_to is None
    assert history.versions[1].identical_to == 1


def test_list_versions_unknown_skill(service):
    """An unknown skill reports not found rather than an empty history."""
    history = service.list_versions("ghost")

    assert history.found is False
    assert history.versions == []
    assert "ghost" in history.message


def test_malformed_republish_leaves_versions_intact(service):
    """4.4 — a rejected update must not disturb what is already published."""
    service.publish({"SKILL.md": V1, "template.md": "keep me\n"})

    rejected = service.publish({"SKILL.md": "---\nname: release-note-draft\n---\n\nNo description.\n"})

    assert rejected.published is False
    history = service.list_versions("release-note-draft")
    assert [v.version for v in history.versions] == [1]
    assert service.retrieve("release-note-draft").files == {"SKILL.md": V1, "template.md": "keep me\n"}


def test_version_numbers_are_assigned_inside_the_transaction(service):
    """4.1 — two versions never share a number, even under a race.

    The number comes from MAX(version) computed inside the write transaction, not
    read beforehand; the primary key is what would catch it if that ever changed.
    """
    service.publish({"SKILL.md": V1})
    manifest_row = (("release-note-draft", 1, "d", None, "now", "hash"),)

    with service.repository._connect() as conn:  # noqa: SLF001 - asserts the constraint itself
        with pytest.raises(sqlite3.IntegrityError):
            conn.executemany(
                "INSERT INTO versions"
                " (skill_name, version, description, publisher, published_at, content_hash)"
                " VALUES (?, ?, ?, ?, ?, ?)",
                manifest_row,
            )
