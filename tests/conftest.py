import pytest

from skills_catalog.repository import SqliteRepository
from skills_catalog.service import CatalogService

MANIFEST = """---
name: release-note-draft
description: Drafts release notes from a set of merged PRs.
---

When asked for release notes, read template.md and fill each section.
"""

TEMPLATE = "## Release {version}\n\n### Added\n\n### Fixed\n"


@pytest.fixture
def service(tmp_path):
    """A catalog backed by a real SQLite file.

    Not mocked: the transaction is the thing most of these tests are about, and a
    fake repository would mock away exactly what is under test.
    """
    return CatalogService(SqliteRepository(tmp_path / "catalog.db"))


@pytest.fixture
def skill():
    return {"SKILL.md": MANIFEST, "template.md": TEMPLATE}
