"""Query handling for discovery.

The assistant turns a developer's need into a query string; this turns that string
into something FTS5 will accept.
"""

import re

# Everything FTS5 treats as syntax rather than text.
_TOKEN = re.compile(r"[A-Za-z0-9_]+")

MAX_LIMIT = 50


def to_match_expression(query: str) -> str | None:
    """Build an FTS5 MATCH expression from free-form natural language.

    A query reaches us as whatever the developer said — "is there a skill for
    release-notes?" — and FTS5 reads quotes, hyphens, asterisks, AND/OR/NOT and NEAR
    as operators, so passing it through raises a syntax error on ordinary questions.
    Tokens are therefore extracted and re-quoted rather than escaped in place.

    Terms are OR-ed: a developer describing a need in a sentence should not have to
    match every word of it. FTS5's rank orders the results, so the skill matching
    more terms still comes first.

    Returns None when nothing searchable remains, which the caller reports as no match
    rather than as an error.
    """
    tokens = _TOKEN.findall(query or "")
    if not tokens:
        return None
    return " OR ".join(f'"{token}"' for token in tokens)


def clamp_limit(limit: int | None, default: int = 10) -> int:
    """Keep a result set small enough to sit in an assistant's context comfortably."""
    if limit is None:
        return default
    return max(1, min(int(limit), MAX_LIMIT))
