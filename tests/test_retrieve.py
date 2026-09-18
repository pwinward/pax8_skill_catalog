"""Requirement 3 — retrieve a skill."""


def test_retrieve_returns_latest_complete(service, skill):
    """3.1 — retrieval without a version returns the latest, manifest and all files."""
    service.publish(skill)

    retrieved = service.retrieve("release-note-draft")

    assert retrieved.found is True
    assert retrieved.version == 1
    assert retrieved.files == skill
