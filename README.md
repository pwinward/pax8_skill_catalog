# Skills Catalog

A shared catalog that AI assistants publish skills to and retrieve them from.

One developer publishes a skill once; another developer's assistant discovers and
retrieves it — no file handoff, no repo to clone, every version kept.

Built as a work-sample exercise from a PRD. The planning artifacts are in `docs/`.

## Quickstart

Needs [uv](https://docs.astral.sh/uv/getting-started/installation/), which installs
its own Python. Nothing else.

```bash
uv run skills-catalog seed     # publish three sample skills
uv run skills-catalog serve    # http://127.0.0.1:8000/mcp
```

Point an assistant at it:

```bash
claude mcp add --transport http skills-catalog http://127.0.0.1:8000/mcp
```

Then ask it: *"is there a skill for writing release notes?"*, and *"get me the
release-note-draft skill."*

Already on Python 3.10+ and would rather not use uv:

```bash
python -m venv .venv && . .venv/bin/activate   # .venv\Scripts\activate on Windows
pip install -e . && pytest
skills-catalog seed && skills-catalog serve
```

## What it does

| Tool | Purpose |
|---|---|
| `publish_skill` | Publish a skill bundle. A name that already exists becomes a new version. |
| `discover_skills` | Find skills matching a described need. Returns name, description, version. |
| `retrieve_skill` | Fetch a skill complete and unchanged. Latest by default, or a given version. |
| `list_skill_versions` | A skill's history: when, by whom, and its content hash. |

A skill is a directory: `SKILL.md` carrying `name` and `description` in frontmatter
with the instructions below it, plus any supporting files. It travels as a map of
relative path to file contents, in both directions — so what is retrieved is
byte-identical to what was published, and writing the map to disk installs the skill.

## How it is built

One process. The MCP server *is* the catalog, so any number of assistants connect to
the same one — which is the point: PRD §1's problem is that skills only exist on their
author's machine, and a catalog embedded in each developer's assistant would reproduce
it while passing every functional requirement.

```
MCP tools (thin)  ->  CatalogService  ->  Repository  ->  SQLite (one file)
```

Domain logic sits below the protocol and knows nothing about MCP. Storage and search
are behind protocols, which is where DynamoDB or OpenSearch would slot in.

Python, the official `mcp` SDK, stdlib `sqlite3` with FTS5 for search. Two direct
dependencies.

## Tests

```bash
uv run pytest
```

98 tests, 96% coverage. `docs/requirements.md` maps every PRD acceptance criterion to
the test that proves it. Notable ones:

- **Round-trip fidelity** against content designed to break naive handling: CRLF line
  endings, unicode, trailing whitespace, empty files, nested paths, and a supporting
  file that is itself YAML frontmatter.
- **Five end-to-end tests** against the catalog running as a separate process over
  real HTTP: two client sessions sharing one catalog, the README quickstart run as a
  sequence, and a skill outliving the process that stored it — the last would be the
  only failure if the catalog quietly became a cache.
- **Hostile search queries** — FTS5 reads quotes, hyphens, `AND`/`OR`/`NEAR` as syntax,
  and a developer's question contains all of them.
- **Property-based round-tripping** — byte fidelity and "no query can raise" are
  universal claims, so `hypothesis` generates against them rather than guessing at
  examples. It found a field-injection bug the hand-written cases missed.

## Measured

Ten tool calls during the `DEMO.md` run: median 0.68 ms, slowest 1.39 ms. PRD §7 asks
for interactive responsiveness without prescribing a number, so each call logs its
duration and the figures are reported rather than asserted in a flaky timing test.

## Known limits

- **Text only.** File contents must be UTF-8; binaries are rejected at publish rather
  than stored in a form retrieval could not return unchanged.
- **Publishing costs tokens proportional to skill size**, since the bundle travels as
  tool arguments. Fine for text skills, wrong for large ones.
- **Executable bits and symlinks do not survive** the path-to-content map.
- **Search is lexical.** A skill described as "release notes" will not match a query
  for "changelog". Semantic search is the top-ranked Phase 2 item.
- **No authentication** (PRD §8), so the namespace is flat and any caller may publish a
  new version of any skill. The publisher field is recorded but unverified.
- **Verified on macOS locally**; CI runs the suite and the quickstart on Ubuntu,
  macOS and Windows.

## Documents

| | |
|---|---|
| `docs/requirements.md` | Acceptance criteria in EARS form, traced to PRD clauses and tests |
| `docs/design.md` | Architecture, schema, tool contracts, flows, mechanisms |
| `docs/tasks.md` | The build plan, each task mapped to requirements |
| `docs/decisions.md` | Decision log in the PRD's own format, including rejected options |
| `docs/phase-2.md` | Answer to PRD §12's Q1 — what is worth building next |
| `DEMO.md` | Transcript of two developers sharing one catalog |

## On AI use

Written with Claude Code, working from the spec in `docs/` rather than from prompts —
the requirements, design and decision log came first and are what the implementation
was built against.

What I did not delegate: the architecture, and the reading of the PRD that drove it.
The load-bearing judgments — that a per-developer store would satisfy every functional
requirement while reproducing the problem the PRD exists to solve; that the manifest
should travel as a file so round-trip fidelity is structural rather than careful; that
a rejected publish must carry no version number — are the ones a reviewer should push
on, and they are mine to defend.

Two things AI caught that I would have missed: that raw natural language reaches FTS5
as syntax, and that a `SKILL.md`-shaped supporting file is a real test case. Two things
I overrode: a proposed concurrency test defending an architectural argument the PRD
never makes, and a latency assertion that would have encoded a threshold PRD §7
deliberately leaves open.
