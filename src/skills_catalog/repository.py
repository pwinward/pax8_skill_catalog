"""SQLite persistence. Insert-only: no code path here mutates a published version."""

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator

from .errors import IntegrityFailure, SkillNotFound
from .hashing import file_sha256
from .models import FileMap, Manifest, SkillRef, VersionInfo, VersionMeta

SCHEMA = """
CREATE TABLE IF NOT EXISTS skills (
  name       TEXT PRIMARY KEY,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS versions (
  skill_name   TEXT    NOT NULL REFERENCES skills(name),
  version      INTEGER NOT NULL,
  description  TEXT    NOT NULL,
  publisher    TEXT,
  published_at TEXT    NOT NULL,
  content_hash TEXT    NOT NULL,
  PRIMARY KEY (skill_name, version)
);

CREATE TABLE IF NOT EXISTS version_files (
  skill_name TEXT    NOT NULL,
  version    INTEGER NOT NULL,
  path       TEXT    NOT NULL,
  content    BLOB    NOT NULL,
  sha256     TEXT    NOT NULL,
  PRIMARY KEY (skill_name, version, path),
  FOREIGN KEY (skill_name, version) REFERENCES versions(skill_name, version)
);

CREATE VIRTUAL TABLE IF NOT EXISTS skills_fts USING fts5(name, description);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class SqliteRepository:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    @contextmanager
    def _connect(self) -> Iterator[sqlite3.Connection]:
        """A connection per operation.

        Queries here are microseconds against a local file and every write is
        serialized through this one process, so pooling would add machinery without
        buying anything. WAL keeps readers from blocking the writer.
        """
        conn = sqlite3.connect(self.db_path, isolation_level=None)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode = WAL")
            conn.execute("PRAGMA foreign_keys = ON")
            conn.execute("PRAGMA busy_timeout = 5000")
            yield conn
        finally:
            conn.close()

    def init_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def insert_version(
        self,
        manifest: Manifest,
        files: FileMap,
        file_hashes: dict[str, str],
        content_hash: str,
        publisher: str | None,
    ) -> int:
        """Write a new version. One transaction covering every row and the search index.

        The version number is computed inside the transaction, not read beforehand:
        two publishes of the same name that both read MAX(version) first would both
        compute the same next number.
        """
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            try:
                now = _now()
                conn.execute(
                    "INSERT OR IGNORE INTO skills (name, created_at) VALUES (?, ?)",
                    (manifest.name, now),
                )
                row = conn.execute(
                    "SELECT COALESCE(MAX(version), 0) + 1 AS next FROM versions WHERE skill_name = ?",
                    (manifest.name,),
                ).fetchone()
                version = int(row["next"])

                conn.execute(
                    "INSERT INTO versions"
                    " (skill_name, version, description, publisher, published_at, content_hash)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (manifest.name, version, manifest.description, publisher, now, content_hash),
                )
                conn.executemany(
                    "INSERT INTO version_files (skill_name, version, path, content, sha256)"
                    " VALUES (?, ?, ?, ?, ?)",
                    [
                        (manifest.name, version, path, content.encode("utf-8"), file_hashes[path])
                        for path, content in files.items()
                    ],
                )
                # The index is a projection of the latest version, so it is replaced
                # rather than appended to.
                conn.execute("DELETE FROM skills_fts WHERE name = ?", (manifest.name,))
                conn.execute(
                    "INSERT INTO skills_fts (name, description) VALUES (?, ?)",
                    (manifest.name, manifest.description),
                )
                conn.execute("COMMIT")
                return version
            except Exception:
                conn.execute("ROLLBACK")
                raise

    def latest_version(self, name: str) -> int | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT MAX(version) AS latest FROM versions WHERE skill_name = ?", (name,)
            ).fetchone()
        return None if row["latest"] is None else int(row["latest"])

    def skill_exists(self, name: str) -> bool:
        with self._connect() as conn:
            return (
                conn.execute("SELECT 1 FROM skills WHERE name = ?", (name,)).fetchone() is not None
            )

    def get_version(self, name: str, version: int) -> tuple[VersionMeta, FileMap]:
        """A version's metadata and its files, read on one connection.

        Both come back together because every caller needs both: the files to return
        and the recorded hash to check them against.
        """
        with self._connect() as conn:
            meta = conn.execute(
                "SELECT version, published_at, publisher, content_hash FROM versions"
                " WHERE skill_name = ? AND version = ?",
                (name, version),
            ).fetchone()
            if meta is None:
                raise SkillNotFound(f"{name} version {version}")
            rows = conn.execute(
                "SELECT path, content, sha256 FROM version_files"
                " WHERE skill_name = ? AND version = ? ORDER BY path",
                (name, version),
            ).fetchall()

        files: FileMap = {}
        for row in rows:
            content = bytes(row["content"]).decode("utf-8")
            if file_sha256(content) != row["sha256"]:
                raise IntegrityFailure(f"{name} v{version}: stored bytes for {row['path']} altered")
            files[row["path"]] = content
        return VersionMeta(**dict(meta)), files

    def list_versions(self, name: str) -> list[VersionInfo]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT version, published_at, publisher, content_hash FROM versions"
                " WHERE skill_name = ? ORDER BY version",
                (name,),
            ).fetchall()
        if not rows:
            raise SkillNotFound(name)

        seen: dict[str, int] = {}
        history: list[VersionInfo] = []
        for row in rows:
            first = seen.setdefault(row["content_hash"], int(row["version"]))
            history.append(
                VersionInfo(
                    version=int(row["version"]),
                    published_at=row["published_at"],
                    publisher=row["publisher"],
                    content_hash=row["content_hash"],
                    identical_to=None if first == int(row["version"]) else first,
                )
            )
        return history

    def search(self, match_expression: str, limit: int) -> list[SkillRef]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT f.name AS name,"
                "       (SELECT description FROM versions v WHERE v.skill_name = f.name"
                "         ORDER BY v.version DESC LIMIT 1) AS description,"
                "       (SELECT MAX(version) FROM versions v WHERE v.skill_name = f.name) AS latest"
                "  FROM skills_fts f WHERE skills_fts MATCH ? ORDER BY rank LIMIT ?",
                (match_expression, limit),
            ).fetchall()
        return [
            SkillRef(name=r["name"], description=r["description"], latest_version=int(r["latest"]))
            for r in rows
        ]
