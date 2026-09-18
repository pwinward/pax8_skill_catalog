"""Requirement 1.6 and 5.1 — the claim the whole design rests on.

PRD §1's pain is that a skill lives only on its author's machine. Every other test
here exercises one client against one service, which a per-developer local store
would also pass. This is the one that would fail if the catalog were not shared.
"""

import asyncio

import pytest
from mcp.client import Client

from tests.conftest import catalog_process

MANIFEST = """---
name: release-note-draft
description: Drafts release notes from a set of merged pull requests.
---

Read template.md and fill each section.
"""
FILES = {"SKILL.md": MANIFEST, "template.md": "## Release {version}\n\n### Added\n"}


def test_two_clients_share_catalog(running_catalog):
    """1.6 — what Developer 1 publishes, Developer 2 discovers and retrieves.

    Two independent client sessions, connected separately, with no shared state
    between them other than the catalog itself.
    """

    async def developer_1_publishes() -> None:
        async with Client(running_catalog) as client:
            result = await client.call_tool(
                "publish_skill", {"files": FILES, "publisher": "developer-1"}
            )
            assert result.structured_content["published"] is True

    async def developer_2_discovers_and_retrieves() -> dict:
        async with Client(running_catalog) as client:
            found = await client.call_tool(
                "discover_skills", {"query": "is there a skill for writing release notes?"}
            )
            names = [s["name"] for s in found.structured_content["result"]]
            assert "release-note-draft" in names

            got = await client.call_tool("retrieve_skill", {"name": "release-note-draft"})
            return got.structured_content

    asyncio.run(developer_1_publishes())
    retrieved = asyncio.run(developer_2_discovers_and_retrieves())

    assert retrieved["found"] is True
    # The whole point: Developer 2 has exactly what Developer 1 published.
    assert retrieved["files"] == FILES


def test_end_to_end_via_mcp_client(running_catalog):
    """5.1 — every requirement is reachable through the assistant-facing surface."""

    async def exercise() -> None:
        async with Client(running_catalog) as client:
            tools = {t.name for t in (await client.list_tools()).tools}
            assert tools == {
                "publish_skill",
                "discover_skills",
                "retrieve_skill",
                "list_skill_versions",
            }

            await client.call_tool("publish_skill", {"files": FILES})
            updated = {**FILES, "SKILL.md": MANIFEST.replace("Read template", "Open template")}
            second = await client.call_tool("publish_skill", {"files": updated})
            assert second.structured_content["version"] == 2

            history = await client.call_tool(
                "list_skill_versions", {"name": "release-note-draft"}
            )
            assert [v["version"] for v in history.structured_content["versions"]] == [1, 2]

            pinned = await client.call_tool(
                "retrieve_skill", {"name": "release-note-draft", "version": 1}
            )
            assert pinned.structured_content["files"] == FILES

            missing = await client.call_tool("retrieve_skill", {"name": "no-such-skill"})
            assert missing.structured_content["found"] is False
            assert missing.is_error is False

    asyncio.run(exercise())


def test_a_published_skill_outlives_the_process_that_stored_it(tmp_path):
    """The catalog is a place skills exist, not a cache in front of one.

    PRD §1's whole complaint is that a skill lives somewhere it can be lost. Every
    other test here builds a server and tears it down inside one test, so a
    regression that stopped persisting — a database opened in memory, a path
    resolved differently — would leave the suite entirely green.
    """
    database = tmp_path / "catalog.db"

    async def publish(url):
        async with Client(url) as client:
            result = await client.call_tool(
                "publish_skill", {"files": FILES, "publisher": "developer-1"}
            )
            return result.structured_content

    async def retrieve(url):
        async with Client(url) as client:
            result = await client.call_tool("retrieve_skill", {"name": "release-note-draft"})
            return result.structured_content

    with catalog_process(database) as url:
        published = asyncio.run(publish(url))
    # The process is gone. A second one, on a different port, reading the same file.
    with catalog_process(database) as url:
        retrieved = asyncio.run(retrieve(url))

    assert retrieved["found"] is True
    assert retrieved["files"] == FILES
    assert retrieved["content_hash"] == published["content_hash"]


def test_a_rejection_survives_the_wire_intact(running_catalog):
    """The structured-result contract (design §6.5) has to hold over HTTP, not just
    in process — that is where a serialization change would quietly drop a field."""

    async def exercise():
        async with Client(running_catalog) as client:
            return await client.call_tool(
                "publish_skill",
                {"files": {"SKILL.md": "---\nname: no-description\n---\n\nBody.\n"}},
            )

    result = asyncio.run(exercise())
    payload = result.structured_content

    assert result.is_error is False
    assert payload["published"] is False
    assert payload["field"] == "description"
    assert payload["message"]
    # Nothing in a rejection can be mistaken for a successful publish.
    assert payload["version"] is None
    assert payload["content_hash"] is None
