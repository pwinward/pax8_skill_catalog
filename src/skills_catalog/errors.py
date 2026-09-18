"""Failures that are not domain outcomes.

A skill that does not exist is an answer (`found: false`). These are not: they mean
the catalog is broken or misused, so they raise rather than returning.
"""


class IntegrityFailure(Exception):
    """Stored bytes do not match the hash recorded when they were published.

    Corruption. Raised rather than returned, because handing back content already
    known to differ from what was published would violate the one guarantee the
    catalog makes about retrieval (PRD §7).
    """


class SkillNotFound(Exception):
    """Internal signal from the repository; the service turns it into found: false."""
