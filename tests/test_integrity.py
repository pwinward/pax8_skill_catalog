"""Requirement 3.2 — what comes back is what went in."""

import pytest

from skills_catalog.repository import IntegrityFailure

MANIFEST = """---
name: fidelity-check
description: A skill whose files exercise byte-level round-tripping.
---

Body text.
"""

AWKWARD_CONTENT = {
    "crlf.md": "line one\r\nline two\r\n",
    "no-trailing-newline.md": "ends abruptly",
    "unicode.md": "café — naïve — 日本語 — 🎉\n",
    "trailing-space.md": "value   \n\n\n",
    "empty.md": "",
    "deep/nested/path/file.md": "nested\n",
    "yaml-lookalike.md": "---\nname: not-a-manifest\n---\n",
}


def test_retrieve_is_byte_identical(service):
    """3.2 — no normalization anywhere: CRLF, unicode, whitespace and empties survive."""
    files = {"SKILL.md": MANIFEST, **AWKWARD_CONTENT}

    service.publish(files)
    retrieved = service.retrieve("fidelity-check")

    assert retrieved.files == files
    for path, content in files.items():
        assert retrieved.files[path] == content, f"{path} was altered in transit"


def test_content_hash_is_stable_across_publish_and_retrieve(service):
    """3.2 — the hash recorded at publish is the hash verified on retrieval."""
    files = {"SKILL.md": MANIFEST, **AWKWARD_CONTENT}

    published = service.publish(files)
    retrieved = service.retrieve("fidelity-check")

    assert retrieved.content_hash == published.content_hash


def test_tampered_storage_raises_rather_than_returning_wrong_content(service, stored):
    """3.2 — altered bytes are caught by the per-file hash."""
    service.publish({"SKILL.md": MANIFEST})

    stored.corrupt_file("SKILL.md", b"tampered with after publication")

    with pytest.raises(IntegrityFailure):
        service.retrieve("fidelity-check")


def test_missing_file_is_caught_by_the_bundle_hash(service, stored):
    """3.2 — a file removed from a version leaves every remaining hash valid.

    Only the bundle hash, which covers the sorted (path, hash) pairs, notices that
    the set of files is no longer what was published.
    """
    service.publish({"SKILL.md": MANIFEST, "template.md": "## Release\n"})

    stored.delete_file("template.md")

    with pytest.raises(IntegrityFailure, match="bundle hash"):
        service.retrieve("fidelity-check")
