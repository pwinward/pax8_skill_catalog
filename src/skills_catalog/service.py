"""Catalog behaviour. Knows nothing about MCP, HTTP, or how it was called."""

from .errors import IntegrityFailure, SkillNotFound
from .hashing import bundle_hash, file_hashes
from .models import FileMap, PublishResult, SkillBundle, SkillRef, VersionHistory
from .repository import SqliteRepository
from .search import clamp_limit, to_match_expression
from .validation import ValidationError, validate_publish


def _no_such_skill(name: str) -> str:
    return f"No skill named '{name}'."


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

        hashes = file_hashes(files)
        content_hash = bundle_hash(hashes)
        version = self.repository.insert_version(
            manifest, files, hashes, content_hash, publisher
        )
        return PublishResult(
            published=True,
            name=manifest.name,
            version=version,
            content_hash=content_hash,
            file_count=len(files),
        )

    def retrieve(self, name: str, version: int | None = None) -> SkillBundle:
        resolved = self._resolve_version(name, version)
        if isinstance(resolved, str):
            return SkillBundle(found=False, name=name, message=resolved)

        meta, files = self.repository.get_version(name, resolved)

        # The repository verified each file against its own stored hash. This checks
        # the bundle as a whole, so a file that went missing or was renamed is caught
        # too. A mismatch is corruption, not a domain outcome: it raises rather than
        # returning content already known to differ from what was published (PRD §7).
        recomputed = bundle_hash(file_hashes(files))
        if recomputed != meta.content_hash:
            raise IntegrityFailure(
                f"{name} v{resolved}: bundle hash {recomputed} does not match "
                f"the hash recorded at publish ({meta.content_hash})"
            )

        return SkillBundle(
            found=True, name=name, version=resolved, content_hash=recomputed, files=files
        )

    def _resolve_version(self, name: str, requested: int | None) -> int | str:
        """Which version to serve, or the reason there is none.

        Returns a version number, or a message explaining why not. An unknown version
        of a known skill reads differently from an unknown skill, so that an assistant
        relaying the answer says which is true (requirement 3.4).
        """
        latest = self.repository.latest_version(name)
        if latest is None:
            return _no_such_skill(name)
        if requested is None:
            return latest
        if not 1 <= requested <= latest:
            return f"Skill '{name}' has no version {requested}. Latest is {latest}."
        return requested

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

    def list_versions(self, name: str) -> VersionHistory:
        """A skill's history: every version ever published, oldest first.

        Versions whose content hash matches an earlier one are marked rather than
        merged. Re-publishing identical content does create a new version (FR-04 has
        no carve-out for it, and de-duplication is out of scope per PRD §8), so the
        marking is what keeps the history honest without suppressing anything.
        """
        try:
            versions = self.repository.list_versions(name)
        except SkillNotFound:
            return VersionHistory(found=False, name=name, message=_no_such_skill(name))
        return VersionHistory(found=True, name=name, versions=versions)
