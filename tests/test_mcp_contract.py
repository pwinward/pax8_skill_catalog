"""Requirement 5.1 — the assistant-facing surface.

Tool names, descriptions and schemas are what a model reads when deciding whether and
how to call. They are prompt text, and they are the only part of this system a model
ever sees, so they are asserted rather than assumed.

In-process rather than over HTTP: this is about the contract, not the transport, and
`test_two_clients.py` covers the wire.
"""

import asyncio

import pytest
from mcp.client import Client

from skills_catalog.repository import SqliteRepository
from skills_catalog.server import build_server
from skills_catalog.service import CatalogService

MANIFEST = """---
name: contract-check
description: A skill used to exercise the MCP tool contract.
---

Body.
"""

READ_ONLY_TOOLS = {"discover_skills", "retrieve_skill", "list_skill_versions"}


@pytest.fixture
def server(tmp_path):
    return build_server(CatalogService(SqliteRepository(tmp_path / "catalog.db")))


def run(server, coro_fn):
    async def main():
        async with Client(server) as client:
            return await coro_fn(client)

    return asyncio.run(main())


def test_every_tool_is_registered(server):
    tools = run(server, lambda c: c.list_tools())

    assert {t.name for t in tools.tools} == READ_ONLY_TOOLS | {"publish_skill"}


def test_only_publish_is_a_writer(server):
    """A client deciding what to confirm with a user relies on these hints."""
    tools = run(server, lambda c: c.list_tools())

    read_only = {t.name for t in tools.tools if t.annotations and t.annotations.read_only_hint}

    assert read_only == READ_ONLY_TOOLS


def test_descriptions_state_the_result_contract(server):
    """Descriptions are prompt text: they must say what an empty or failed result means.

    A model that has only been told what a tool does, and not what its answers mean,
    is the one that fills a silence with a guess.
    """
    tools = {t.name: t.description or "" for t in run(server, lambda c: c.list_tools()).tools}

    assert "empty list" in tools["discover_skills"].lower()
    assert "found=false" in tools["retrieve_skill"].lower()
    assert "published=false" in tools["publish_skill"].lower()
    for name, description in tools.items():
        assert len(description) > 100, f"{name} description is too thin to guide a model"


def test_schemas_expose_the_documented_arguments(server):
    tools = {t.name: t.input_schema for t in run(server, lambda c: c.list_tools()).tools}

    assert set(tools["publish_skill"]["properties"]) == {"files", "publisher"}
    assert set(tools["discover_skills"]["properties"]) == {"query", "limit"}
    assert set(tools["retrieve_skill"]["properties"]) == {"name", "version"}
    assert set(tools["list_skill_versions"]["properties"]) == {"name"}
    # Only the identifying arguments are mandatory; the rest have defaults.
    assert tools["retrieve_skill"]["required"] == ["name"]


def test_domain_outcomes_are_results_not_protocol_errors(server):
    """The catalog answering 'no' is a successful call (design §6.5)."""

    async def exercise(client):
        return [
            await client.call_tool("retrieve_skill", {"name": "absent"}),
            await client.call_tool("discover_skills", {"query": "nothing matches this"}),
            await client.call_tool("publish_skill", {"files": {"a.md": "no manifest"}}),
            await client.call_tool("list_skill_versions", {"name": "absent"}),
        ]

    for result in run(server, exercise):
        assert result.is_error is False, "a domain outcome was raised as a protocol error"


def test_a_rejected_publish_carries_nothing_that_reads_as_success(server):
    """Even skimmed, the result must contain no version number (design §6.5)."""

    async def exercise(client):
        return await client.call_tool("publish_skill", {"files": {"a.md": "no manifest"}})

    payload = run(server, exercise).structured_content

    assert payload["published"] is False
    assert payload["version"] is None
    assert payload["content_hash"] is None
    assert payload["message"]


def test_a_bundle_survives_the_json_boundary(server):
    """Serialization is where byte fidelity would quietly break."""
    files = {
        "SKILL.md": MANIFEST,
        "crlf.md": "one\r\ntwo\r\n",
        "unicode.md": "café — 日本語 — 🎉\n",
        "empty.md": "",
        "deep/nested/file.md": "nested\n",
    }

    async def exercise(client):
        await client.call_tool("publish_skill", {"files": files})
        return await client.call_tool("retrieve_skill", {"name": "contract-check"})

    assert run(server, exercise).structured_content["files"] == files


def test_the_server_identifies_itself(server):
    """serverInfo is what a client shows a user when listing connected servers.

    An empty version reads as a broken install, and it is what a bug report would
    quote back.
    """
    async def read_info(client):
        return client.server_info

    identity = run(server, read_info)

    assert identity.name == "skills-catalog"
    assert identity.version, "server reports no version"
