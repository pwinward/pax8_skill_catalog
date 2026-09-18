"""Catalog behaviour. Knows nothing about MCP, HTTP, or how it was called."""

from .hashing import bundle_hash
from .models import FileMap, PublishResult, SkillBundle
from .repository import SkillNotFound, SqliteRepository
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

        stored_hash = bundle_hash(files)
        return SkillBundle(
            found=True, name=name, version=resolved, content_hash=stored_hash, files=files
        )
