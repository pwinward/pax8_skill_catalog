"""Requirement 3 — retrieve a skill."""


def test_retrieve_returns_latest_complete(service, skill):
    """3.1 — retrieval without a version returns the latest, manifest and all files."""
    service.publish(skill)

    retrieved = service.retrieve("release-note-draft")

    assert retrieved.found is True
    assert retrieved.version == 1
    assert retrieved.files == skill


def test_retrieve_unknown_returns_not_found(service, skill):
    """3.3 — an unknown skill is an explicit answer, not an error and not a guess."""
    service.publish(skill)

    result = service.retrieve("no-such-skill")

    assert result.found is False
    assert "no-such-skill" in result.message
    # Nothing partial comes back alongside found: false.
    assert result.files is None
    assert result.version is None


def test_not_found_is_returned_not_raised(service):
    """3.3 — the catalog answering 'no' is a successful call, so a tool result carries it."""
    result = service.retrieve("never-published")

    assert result.found is False
    assert result.message
