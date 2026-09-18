"""Requirement 1.6 and 5.1 — the claim the whole design rests on.

PRD §1's pain is that a skill lives only on its author's machine. Every other test
here exercises one client against one service, which a per-developer local store
would also pass. This is the one that would fail if the catalog were not shared.
"""

import asyncio
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest
from mcp.client import Client

MANIFEST = """---
name: release-note-draft
description: Drafts release notes from a set of merged pull requests.
---

Read template.md and fill each section.
"""
FILES = {"SKILL.md": MANIFEST, "template.md": "## Release {version}\n\n### Added\n"}


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait_until_listening(port: int, timeout: float = 30.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket() as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.1)
    return False


@pytest.fixture
def running_catalog(tmp_path):
    """The catalog as a separate process, the way two developers would meet it."""
    port = _free_port()
    process = subprocess.Popen(
        [sys.executable, "-m", "skills_catalog", "--db", str(tmp_path / "catalog.db"),
         "serve", "--port", str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
    )
    try:
        if not _wait_until_listening(port):
            pytest.fail("catalog did not start")
        yield f"http://127.0.0.1:{port}/mcp"
    finally:
        process.terminate()
        process.wait(timeout=10)


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
