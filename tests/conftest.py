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


@pytest.fixture
def stored(service):
    """Read the catalog's storage directly.

    Some assertions are about what is *not* there — a rejected publish must leave no
    row anywhere — which cannot be shown through the service's own API. This keeps
    that coupling in one place instead of in each test that needs it.
    """

    class Stored:
        TABLES = ("skills", "versions", "version_files", "skills_fts")

        def row_counts(self) -> dict[str, int]:
            with service.repository._connect() as conn:
                return {
                    table: conn.execute(f"SELECT COUNT(*) AS n FROM {table}").fetchone()["n"]
                    for table in self.TABLES
                }

        def is_empty(self) -> bool:
            return all(count == 0 for count in self.row_counts().values())

        def corrupt_file(self, path: str, content: bytes) -> None:
            """Alter stored bytes behind the service's back, to prove detection."""
            with service.repository._connect() as conn:
                conn.execute("UPDATE version_files SET content = ? WHERE path = ?", (content, path))

        def delete_file(self, path: str) -> None:
            """Remove a file from a stored version, leaving its per-file hash valid."""
            with service.repository._connect() as conn:
                conn.execute("DELETE FROM version_files WHERE path = ?", (path,))

    return Stored()
