"""Content hashing. The bundle hash is what makes 'complete and unchanged' checkable."""

import hashlib

from .models import FileMap


def file_sha256(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def bundle_hash(files: FileMap) -> str:
    """Hash the sorted (path, file hash) pairs.

    Paths are part of the hash because a skill's instructions refer to its files by
    path: moving template.md would leave the body pointing at nothing while every
    file's bytes stayed identical. Because the manifest is itself one of the files,
    this covers everything the author sent, with no separate metadata to keep in step.
    """
    digest = hashlib.sha256()
    for path in sorted(files):
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(file_sha256(files[path]).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()
