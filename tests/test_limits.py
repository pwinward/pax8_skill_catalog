"""Requirement 1.4 — the guards that stop one publish exhausting the catalog.

These branches are enforced but easy to delete in a refactor without any other test
noticing, which is exactly why they are tested here.
"""

import pytest

from skills_catalog.validation import MAX_BUNDLE_BYTES, MAX_FILE_BYTES, MAX_FILES

MANIFEST = """---
name: limits
description: A skill used to exercise the publish limits.
---

Body.
"""


def test_file_count_at_the_limit_is_accepted(service):
    files = {"SKILL.md": MANIFEST, **{f"f{i}.md": "x" for i in range(MAX_FILES - 1)}}

    assert service.publish(files).published is True


def test_file_count_over_the_limit_is_rejected(service):
    files = {"SKILL.md": MANIFEST, **{f"f{i}.md": "x" for i in range(MAX_FILES)}}

    result = service.publish(files)

    assert result.published is False
    assert result.field == "files"
    assert str(MAX_FILES) in result.message


def test_single_file_over_the_size_limit_is_rejected(service):
    result = service.publish({"SKILL.md": MANIFEST, "big.md": "x" * (MAX_FILE_BYTES + 1)})

    assert result.published is False
    assert "big.md" in result.message


def test_bundle_over_the_total_size_limit_is_rejected(service):
    """No single file exceeds its own limit; together they exceed the bundle limit."""
    chunk = "x" * (MAX_FILE_BYTES - 1)
    files = {"SKILL.md": MANIFEST}
    while sum(len(v.encode()) for v in files.values()) <= MAX_BUNDLE_BYTES:
        files[f"chunk{len(files)}.md"] = chunk

    result = service.publish(files)

    assert result.published is False
    assert "Bundle is" in result.message


def test_size_is_measured_in_bytes_not_characters(service):
    """A multibyte character must count for what it costs to store."""
    multibyte = "é" * MAX_FILE_BYTES  # 2 bytes each, so twice the limit

    result = service.publish({"SKILL.md": MANIFEST, "unicode.md": multibyte})

    assert result.published is False


@pytest.mark.parametrize("bad_path", ["null\x00byte.md", "trailing\x00"])
def test_null_bytes_in_paths_are_rejected(service, bad_path):
    """A null byte truncates a path in some filesystem APIs."""
    result = service.publish({"SKILL.md": MANIFEST, bad_path: "x"})

    assert result.published is False
    assert "null byte" in result.message


@pytest.mark.parametrize(
    "frontmatter",
    [
        "---\nname: n\n  bad indentation here\ndescription: d\n---\n\nBody.\n",
        "---\nname: n\ndescription: d\n- a list item\n---\n\nBody.\n",
    ],
)
def test_unsupported_frontmatter_is_reported_not_guessed_at(service, frontmatter):
    """Structure the parser does not support is refused rather than mis-read."""
    result = service.publish({"SKILL.md": frontmatter})

    assert result.published is False
    assert result.field == "SKILL.md"


def test_frontmatter_comments_are_ignored(service):
    result = service.publish(
        {"SKILL.md": "---\n# a comment\nname: commented\ndescription: d\n---\n\nBody.\n"}
    )

    assert result.published is True
    assert result.name == "commented"
