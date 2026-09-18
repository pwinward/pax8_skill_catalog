"""Requirement 1 — publish a skill."""


def test_publish_stores_and_confirms(service, skill):
    """1.1 — a valid bundle is stored and the assigned version returned."""
    result = service.publish(skill, publisher="developer-1")

    assert result.published is True
    assert result.name == "release-note-draft"
    assert result.version == 1
    assert result.file_count == 2
    assert result.content_hash


def test_publish_round_trips_supporting_files(service, skill):
    """1.2 — supporting files are stored and come back complete."""
    service.publish(skill)

    retrieved = service.retrieve("release-note-draft")

    assert retrieved.files == skill
    assert set(retrieved.files) == {"SKILL.md", "template.md"}
