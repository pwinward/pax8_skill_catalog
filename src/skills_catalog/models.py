"""Types crossing the service boundary. Pydantic so the MCP layer derives schemas from them."""

from pydantic import BaseModel, Field

FileMap = dict[str, str]


class Manifest(BaseModel):
    """The parsed contents of SKILL.md. Never re-serialized — the file itself is stored."""

    name: str
    description: str
    body: str


class PublishResult(BaseModel):
    published: bool
    name: str | None = None
    version: int | None = None
    content_hash: str | None = None
    file_count: int | None = None
    # Set only on rejection. A rejected publish carries no version number, so there is
    # nothing in the result that could be relayed as a success (design D-11).
    field: str | None = None
    message: str | None = None


class SkillBundle(BaseModel):
    found: bool
    name: str | None = None
    version: int | None = None
    content_hash: str | None = None
    files: FileMap | None = None
    message: str | None = None


class SkillRef(BaseModel):
    """A discovery result. Deliberately thin: no body, no file contents (requirement 2.3)."""

    name: str
    description: str
    latest_version: int


class VersionMeta(BaseModel):
    """A version's stored metadata, as the repository reads it back."""

    version: int
    published_at: str
    publisher: str | None = None
    content_hash: str


class VersionInfo(BaseModel):
    version: int
    published_at: str
    publisher: str | None = None
    content_hash: str
    identical_to: int | None = Field(
        default=None,
        description="Set when this version's content hash matches an earlier version.",
    )


class VersionHistory(BaseModel):
    found: bool
    name: str
    versions: list[VersionInfo] = Field(default_factory=list)
    message: str | None = None
