"""The commands a reviewer runs first, and the observability that backs requirement 6.1."""

import json

import pytest

from skills_catalog.cli import SEED_DIR, load_skill_directory, main, seed
from skills_catalog.observability import logged


def test_seed_publishes_every_sample_skill(service, capsys):
    """Step one of the README quickstart. If this breaks, the reviewer's first command does."""
    assert seed(service, SEED_DIR) == 0

    published = capsys.readouterr().out
    for name in ("release-note-draft", "k8s-pod-triage", "pr-description"):
        assert name in published
        assert service.retrieve(name).found is True


def test_seed_skills_are_discoverable_by_what_they_are_for(service):
    """The samples exist to demonstrate discovery, so their descriptions must earn a match."""
    seed(service, SEED_DIR)

    assert "release-note-draft" in [s.name for s in service.discover("release notes")]
    assert "k8s-pod-triage" in [s.name for s in service.discover("kubernetes pod failing")]


def test_seed_reports_a_missing_directory_rather_than_failing_silently(service, tmp_path):
    assert seed(service, tmp_path / "nowhere") == 1


def test_load_skill_directory_preserves_nested_paths(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / "SKILL.md").write_text("manifest", encoding="utf-8")
    (tmp_path / "scripts" / "run.py").write_text("code", encoding="utf-8")

    files = load_skill_directory(tmp_path)

    assert files == {"SKILL.md": "manifest", "scripts/run.py": "code"}


def test_cli_seeds_into_the_named_database(tmp_path, capsys):
    """End to end through the argument parser, as the README invokes it."""
    database = tmp_path / "catalog.db"

    assert main(["--db", str(database), "seed"]) == 0
    assert database.exists()
    assert "release-note-draft" in capsys.readouterr().out


class TestObservability:
    """Requirement 6.1 — responsiveness is measured, so the measurement must exist."""

    def test_a_successful_call_logs_its_duration(self, capsys):
        with logged("retrieve_skill", skill="x") as record:
            record["outcome"] = "found"

        entry = json.loads(capsys.readouterr().out)
        assert entry["tool"] == "retrieve_skill"
        assert entry["outcome"] == "found"
        assert isinstance(entry["duration_ms"], float)

    def test_an_unset_outcome_defaults_rather_than_going_missing(self, capsys):
        with logged("discover_skills"):
            pass

        assert json.loads(capsys.readouterr().out)["outcome"] == "ok"

    def test_a_raising_call_is_logged_and_still_raises(self, capsys):
        with pytest.raises(ValueError):
            with logged("publish_skill"):
                raise ValueError("boom")

        entry = json.loads(capsys.readouterr().out)
        assert entry["outcome"] == "error"
        assert entry["error"] == "ValueError"
        assert "duration_ms" in entry

    def test_file_contents_never_reach_the_log(self, service, capsys):
        """A publish would otherwise put whole skill files into stdout."""
        secret = "a-value-that-must-not-be-logged"
        with logged("publish_skill", file_count=2) as record:
            record["outcome"] = "published"

        assert secret not in capsys.readouterr().out
