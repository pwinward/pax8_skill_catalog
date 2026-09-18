"""Requirement 2 — discover skills through an AI assistant."""

import pytest

RELEASE_NOTES = """---
name: release-note-draft
description: Drafts release notes from a set of merged pull requests.
---

Read template.md and fill each section.
"""

KUBERNETES = """---
name: k8s-triage
description: Diagnoses common Kubernetes pod and node failures.
---

Check pod status first.
"""


@pytest.fixture
def populated(service):
    service.publish({"SKILL.md": RELEASE_NOTES, "template.md": "## Release\n"})
    service.publish({"SKILL.md": KUBERNETES})
    return service


def test_discover_returns_matches(populated):
    """2.1 — a described need finds the skill that serves it."""
    results = populated.discover("release notes")

    assert [r.name for r in results] == ["release-note-draft"]


def test_discover_returns_name_and_description(populated):
    """2.2 — every result identifies the skill."""
    results = populated.discover("kubernetes")

    assert results[0].name == "k8s-triage"
    assert results[0].description == "Diagnoses common Kubernetes pod and node failures."
    assert results[0].latest_version == 1


def test_discover_results_are_thin(populated):
    """2.3 — no bodies, no file contents: results land in the assistant's context."""
    results = populated.discover("release notes")

    fields = results[0].model_dump()
    assert set(fields) == {"name", "description", "latest_version"}
    assert "template.md" not in str(fields)


def test_discover_no_match_returns_empty(populated):
    """2.4 — nothing matching is an empty success, not an error."""
    assert populated.discover("quantum chromodynamics") == []


@pytest.mark.parametrize(
    "query",
    [
        "is there a skill for release-notes?",
        '"release notes"',
        "release AND notes OR NOT kubernetes",
        "release*",
        "NEAR(release notes)",
        "release (notes",
        "skill for: release/notes",
        "^release",
    ],
)
def test_natural_language_never_raises_a_syntax_error(populated, query):
    """2.1 — FTS5 reads punctuation and AND/OR/NEAR as syntax; real questions contain both.

    A developer asking their assistant a plain question must not produce
    sqlite3.OperationalError: fts5: syntax error.
    """
    results = populated.discover(query)

    assert isinstance(results, list)


def test_empty_query_returns_no_match_rather_than_failing(populated):
    """2.4 — nothing searchable is the same answer as nothing matching."""
    assert populated.discover("   ") == []


def test_limit_is_clamped(populated):
    """A caller cannot ask for an unbounded result set."""
    assert len(populated.discover("skill OR release OR kubernetes", limit=10_000)) <= 50
    assert len(populated.discover("release notes", limit=0)) <= 1


def test_index_reflects_the_latest_version_not_every_version(populated):
    """design §6.4 — the index is a projection of the latest version, replaced on publish.

    If it were appended to, the old description would keep matching and a skill would
    appear twice in results.
    """
    revised = RELEASE_NOTES.replace(
        "Drafts release notes from a set of merged pull requests.",
        "Assembles a changelog from merged pull requests.",
    )
    populated.publish({"SKILL.md": revised})

    by_new_wording = populated.discover("changelog")

    assert [s.name for s in by_new_wording] == ["release-note-draft"]
    assert by_new_wording[0].description == "Assembles a changelog from merged pull requests."
    # "Drafts" appeared only in the superseded description, so a match on it would mean
    # the old row is still in the index. ("release" would still match via the name.)
    assert populated.discover("drafts") == []


def test_a_skill_appears_once_however_many_versions_it_has(populated):
    for _ in range(3):
        populated.publish({"SKILL.md": RELEASE_NOTES})

    results = populated.discover("release notes")

    assert [s.name for s in results] == ["release-note-draft"]
    assert results[0].latest_version == 4
