"""The README, executed.

A reviewer's first contact with this system is two commands and a question asked
through an assistant. Those commands are tested individually elsewhere; this runs them
in the order the README gives them, against one database, in separate processes — which
is the only thing that catches a break in the seam between them.
"""

import asyncio
import os
import subprocess
import sys
from pathlib import Path

from mcp.client import Client

from tests.test_two_clients import catalog_process

SEEDED_SKILLS = {"release-note-draft", "k8s-pod-triage", "pr-description"}


def test_seed_then_serve_then_retrieve(tmp_path):
    """`skills-catalog seed`, then `skills-catalog serve`, then an assistant asks."""
    database = tmp_path / "catalog.db"

    seeding = subprocess.run(
        [sys.executable, "-m", "skills_catalog", "--db", str(database), "seed"],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")},
    )
    assert seeding.returncode == 0, seeding.stderr
    assert SEEDED_SKILLS <= set(seeding.stdout.split())

    async def what_a_developer_would_ask(url):
        async with Client(url) as client:
            found = await client.call_tool(
                "discover_skills", {"query": "is there a skill for writing release notes?"}
            )
            names = [s["name"] for s in found.structured_content["result"]]
            assert "release-note-draft" in names, names

            got = await client.call_tool("retrieve_skill", {"name": "release-note-draft"})
            return got.structured_content

    with catalog_process(database) as url:
        skill = asyncio.run(what_a_developer_would_ask(url))

    assert skill["found"] is True
    # Every seeded file comes back, including the supporting template.
    assert set(skill["files"]) == {"SKILL.md", "template.md"}
    assert skill["files"]["SKILL.md"].startswith("---\nname: release-note-draft")
