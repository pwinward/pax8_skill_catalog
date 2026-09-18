"""Manifest parsing and publish validation.

Everything here runs before the transaction opens, so a rejected publish cannot
write anything (requirement 1.5).
"""

import re
from posixpath import normpath

from .models import FileMap, Manifest

MANIFEST_PATH = "SKILL.md"

# Caps exist so one publish cannot exhaust the catalog. Generous for text skills;
# the numbers are arbitrary and stated rather than hidden.
MAX_FILES = 100
MAX_FILE_BYTES = 1_000_000
MAX_BUNDLE_BYTES = 5_000_000

_SLUG = re.compile(r"\A[a-z0-9]+(?:-[a-z0-9]+)*\Z")

_FRONTMATTER = re.compile(r"\A---[ \t]*\r?\n(.*?)\r?\n---[ \t]*\r?\n?(.*)\Z", re.DOTALL)
_KEY_VALUE = re.compile(r"\A([A-Za-z_][A-Za-z0-9_-]*)\s*:\s*(.*)\Z")


class ValidationError(Exception):
    """A publish the caller must fix. Carries the offending field so a retry is informed."""

    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field
        self.message = message


def parse_manifest(text: str) -> Manifest:
    """Read name and description out of SKILL.md frontmatter, plus the instruction body.

    Deliberately not a general YAML parser: a skill manifest's frontmatter is flat
    scalar keys, and pulling in a YAML dependency to read two of them would be a poor
    trade. Unsupported structure is reported rather than silently mis-parsed.
    """
    match = _FRONTMATTER.match(text)
    if not match:
        raise ValidationError(
            MANIFEST_PATH,
            f"{MANIFEST_PATH} must open with a '---' delimited frontmatter block "
            "carrying at least 'name' and 'description'.",
        )

    front, body = match.group(1), match.group(2)
    fields: dict[str, str] = {}
    for line in front.splitlines():
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        kv = _KEY_VALUE.match(line.strip())
        if not kv:
            raise ValidationError(
                MANIFEST_PATH,
                f"Frontmatter line is not a 'key: value' pair: {line.strip()!r}",
            )
        fields[kv.group(1).lower()] = kv.group(2).strip().strip("'\"")

    for key in ("name", "description"):
        if not fields.get(key, "").strip():
            raise ValidationError(key, f"{MANIFEST_PATH} frontmatter is missing '{key}'.")
    if not body.strip():
        raise ValidationError("body", f"{MANIFEST_PATH} has no instruction body below the frontmatter.")

    return Manifest(name=fields["name"].strip(), description=fields["description"].strip(), body=body)


def _validate_path(path: str) -> str:
    """Reject anything that would not land where it claims to, and return the normal form.

    Paths are attacker-controlled input that a retrieving assistant writes to disk, so
    traversal and absolute paths are rejected here rather than trusted downstream.
    """
    if not path or not path.strip():
        raise ValidationError("files", "A file path cannot be empty.")
    if "\x00" in path:
        raise ValidationError("files", f"File path contains a null byte: {path!r}")
    if path.startswith("/") or re.match(r"\A[A-Za-z]:", path):
        raise ValidationError("files", f"File paths must be relative to the skill root: {path!r}")
    if "\\" in path:
        raise ValidationError(
            "files", f"Use forward slashes in file paths: {path!r}"
        )

    normalized = normpath(path)
    if normalized.startswith("..") or normalized.startswith("/"):
        raise ValidationError("files", f"File path escapes the skill directory: {path!r}")
    return normalized


def validate_publish(files: FileMap) -> Manifest:
    """Validate a bundle and return its manifest. Raises ValidationError on the first fault.

    Runs in full before any transaction opens, so a rejected publish cannot leave a
    partial skill behind (requirement 1.5).
    """
    if not files:
        raise ValidationError("files", "A publish must include at least SKILL.md.")
    if MANIFEST_PATH not in files:
        raise ValidationError(
            MANIFEST_PATH, f"A publish must include {MANIFEST_PATH} at the bundle root."
        )
    if len(files) > MAX_FILES:
        raise ValidationError(
            "files", f"A skill may contain at most {MAX_FILES} files; got {len(files)}."
        )

    total = 0
    seen: dict[str, str] = {}
    for path, content in files.items():
        if not isinstance(content, str):
            # Anything not decodable as text cannot survive a JSON round trip, so it is
            # refused rather than stored in a form retrieval could not return unchanged.
            raise ValidationError("files", f"File contents must be UTF-8 text: {path!r}")

        normalized = _validate_path(path)
        # Compared case-insensitively because macOS and Windows filesystems are, so
        # two paths differing only in case would collide when written to disk.
        key = normalized.casefold()
        if key in seen:
            raise ValidationError(
                "files", f"Duplicate file path after normalization: {path!r} and {seen[key]!r}"
            )
        seen[key] = path

        size = len(content.encode("utf-8"))
        if size > MAX_FILE_BYTES:
            raise ValidationError("files", f"{path!r} is {size} bytes; limit is {MAX_FILE_BYTES}.")
        total += size

    if total > MAX_BUNDLE_BYTES:
        raise ValidationError("files", f"Bundle is {total} bytes; limit is {MAX_BUNDLE_BYTES}.")

    manifest = parse_manifest(files[MANIFEST_PATH])
    if not _SLUG.match(manifest.name):
        raise ValidationError(
            "name",
            f"Skill name must be a lowercase slug (letters, digits, hyphens): {manifest.name!r}",
        )
    return manifest
