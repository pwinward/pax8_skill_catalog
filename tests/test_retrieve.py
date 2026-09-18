"""Requirement 3 — retrieve a skill."""

import pytest



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


@pytest.mark.parametrize("bad_version", [0, -1, 999])
def test_out_of_range_versions_report_the_actual_range(service, skill, bad_version):
    """3.4 — a version that cannot exist is reported against what does exist."""
    service.publish(skill)

    result = service.retrieve("release-note-draft", version=bad_version)

    assert result.found is False
    assert f"no version {bad_version}" in result.message
    assert "Latest is 1" in result.message
