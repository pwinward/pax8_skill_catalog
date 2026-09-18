"""Catalog behaviour. Knows nothing about MCP, HTTP, or how it was called."""

from .hashing import bundle_hash
from .models import FileMap, PublishResult, SkillBundle, SkillRef
from .repository import IntegrityFailure, SkillNotFound, SqliteRepository
from .search import clamp_limit, to_match_expression
from .validation import ValidationError, validate_publish


class CatalogService:
    def __init__(self, repository: SqliteRepository) -> None:
        self.repository = repository

    def publish(self, files: FileMap, publisher: str | None = None) -> PublishResult:
        try:
            manifest = validate_publish(files)
        except ValidationError as error:
            # Rejections are returned, not raised: the caller must fix something, and
            # the result carries no version number so nothing here reads as success.
            return PublishResult(published=False, field=error.field, message=error.message)

        content_hash = bundle_hash(files)
        version = self.repository.insert_version(manifest, files, content_hash, publisher)
        return PublishResult(
            published=True,
            name=manifest.name,
            version=version,
            content_hash=content_hash,
            file_count=len(files),
        )

    def retrieve(self, name: str, version: int | None = None) -> SkillBundle:
        resolved = version if version is not None else self.repository.latest_version(name)
        if resolved is None:
            return SkillBundle(found=False, name=name, message=f"No skill named '{name}'.")

        try:
            _, files = self.repository.get_version(name, resolved)
        except SkillNotFound:
            # An unknown version of a known skill is a different answer from an
            # unknown skill, and saying so stops the caller guessing (requirement 3.4).
            if self.repository.skill_exists(name):
                latest = self.repository.latest_version(name)
                return SkillBundle(
                    found=False,
                    name=name,
                    message=f"Skill '{name}' has no version {resolved}. Latest is {latest}.",
                )
            return SkillBundle(found=False, name=name, message=f"No skill named '{name}'.")

        # The per-file hashes were checked on the way out of the repository; this
        # checks the bundle as a whole, so a missing or renamed file is caught too.
        # A mismatch is corruption, not a domain outcome: it raises rather than
        # returning content already known to be wrong (PRD §7).
        row = self.repository.version_meta(name, resolved)
        recomputed = bundle_hash(files)
        if recomputed != row["content_hash"]:
            raise IntegrityFailure(
                f"{name} v{resolved}: bundle hash {recomputed} does not match "
                f"the hash recorded at publish ({row['content_hash']})"
            )
        return SkillBundle(
            found=True, name=name, version=resolved, content_hash=recomputed, files=files
        )

    def discover(self, query: str, limit: int | None = None) -> list[SkillRef]:
        """Find published skills matching a described need.

        Results are deliberately thin — name, description, latest version — because
        they land in the assistant's context on every search. Instruction bodies would
        crowd out the conversation they are meant to serve; retrieval is where the
        full bundle is paid for (requirement 2.3).
        """
        expression = to_match_expression(query)
        if expression is None:
            return []
        return self.repository.search(expression, clamp_limit(limit))
