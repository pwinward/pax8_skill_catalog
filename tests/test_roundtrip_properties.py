"""Requirement 3.2 as a property rather than a list of examples.

`test_integrity.py` checks content chosen because it looked likely to break: CRLF,
unicode, trailing whitespace. That is guessing at an adversary. The actual requirement
is universal — *any* text a developer publishes comes back unchanged — and that is a
property, so it is generated rather than enumerated.
"""

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

MANIFEST = """---
name: property-check
description: A skill whose supporting files are generated.
---

Body.
"""

# Any text, including control characters, newlines and astral-plane codepoints.
# Surrogates are excluded: they cannot be encoded as UTF-8, so they are rejected at
# publish by design rather than round-tripped (decisions D-09).
file_content = st.text(
    alphabet=st.characters(blacklist_categories=("Cs",)),
    max_size=200,
)

# Relative POSIX paths with no traversal and no duplicates after case folding.
path_segment = st.text(
    alphabet=st.characters(whitelist_categories=("Ll", "Nd"), whitelist_characters="-_"),
    min_size=1,
    max_size=12,
).filter(lambda s: s not in (".", ".."))

file_path = st.lists(path_segment, min_size=1, max_size=3).map("/".join).filter(
    lambda p: p.casefold() != "skill.md"
)


@settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(files=st.dictionaries(file_path, file_content, max_size=6))
def test_any_text_survives_publish_and_retrieval_unchanged(service, files):
    bundle = {"SKILL.md": MANIFEST, **files}

    published = service.publish(bundle)
    assert published.published is True, published.message

    retrieved = service.retrieve("property-check")

    assert retrieved.files == bundle
    assert retrieved.content_hash == published.content_hash


@settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(query=st.text(max_size=80))
def test_no_query_can_produce_a_search_error(service, query):
    """FTS5 reads much of ordinary punctuation as syntax; a question must never raise."""
    service.publish({"SKILL.md": MANIFEST})

    assert isinstance(service.discover(query), list)


@settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    description=st.text(min_size=1, max_size=60)
    .map(str.strip)
    .filter(lambda s: s and "\n" not in s and "\r" not in s)
    # A value wrapped in a matched pair of quotes is unwrapped by design, so those are
    # excluded here and covered by example in test_validation.py instead.
    .filter(lambda s: not (len(s) >= 2 and s[0] == s[-1] and s[0] in "'\""))
)
def test_a_description_reaches_discovery_exactly_as_written(service, description):
    """The description is what a developer reads when choosing a skill, so it must not
    be altered in transit.

    This is the property the quote-stripping bug violated: str.strip("'\"") took the
    leading quote off `"Quoted" and more` and left the trailing one, so what was shown
    was not what was written.
    """
    result = service.publish(
        {"SKILL.md": f"---\nname: property-check\ndescription: {description}\n---\n\nBody.\n"}
    )
    assert result.published is True, result.message

    [found] = service.discover("property-check")

    assert found.description == description
