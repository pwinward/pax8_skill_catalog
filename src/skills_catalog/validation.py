"""Manifest parsing and publish validation.

Everything here runs before the transaction opens, so a rejected publish cannot
write anything (requirement 1.5).
"""

import re

from .models import FileMap, Manifest

MANIFEST_PATH = "SKILL.md"

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


def validate_publish(files: FileMap) -> Manifest:
    """Validate a bundle and return its manifest. Raises ValidationError on the first fault."""
    if not files:
        raise ValidationError("files", "A publish must include at least SKILL.md.")
    if MANIFEST_PATH not in files:
        raise ValidationError(
            MANIFEST_PATH, f"A publish must include {MANIFEST_PATH} at the bundle root."
        )
    return parse_manifest(files[MANIFEST_PATH])
