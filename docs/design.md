# Design — Skills Catalog

Companion to `requirements.md`. Covers Phase 1 (P0) only.

References written `PRD §n` point to the Skills Catalog PRD. A bare `§n` points to a section of this document.

## 1. Shape

One long-running service that speaks MCP over HTTP. Any number of assistants connect to it.

```
  Developer 1's assistant          Developer 2's assistant
            |                                |
            +-------- MCP over HTTP ---------+
                             |
        +--------------------v---------------------+
        |        Skills Catalog (one process)      |
        |                                          |
        |    MCP tools (thin)           CLI        |
        |          \                   /  serve    |
        |           v                 v   seed     |
        |               CatalogService             |
        |                     |                    |
        |                Repository                |
        |                     |                    |
        |            SQLite (single file)          |
        +------------------------------------------+
```

The CLI is an in-process entry point, not a network client: `serve` starts the service, `seed` loads sample skills through the same `CatalogService` the tools use.

## 2. Why a service rather than a local store

PRD §1 states the pain precisely: "a skill lives locally, on the author's own machine, there's no shared place it exists." A catalog embedded in each developer's assistant would satisfy every functional requirement and still reproduce that pain, because Developer 1 would publish into their copy and Developer 2 would search theirs.

So the catalog is a process that outlives any assistant session and that multiple assistants reach. Locally that is one command; in production it is the same service behind a gateway. Running it locally satisfies PRD §9's self-containment without weakening the claim.

The shape also buys a property the PRD never asks for. Concurrent publishing is nowhere in the requirements — the use cases are sequential — but with one service in front of the database there is exactly one writer, so the atomicity in §6.1 and the version assignment in §6.3 hold under simultaneous publishes without any locking machinery. Two assistant-local servers sharing a database file would need WAL mode and a busy timeout to get the same result. Not a requirement met; a failure mode avoided for free.

## 3. Layering

| Layer | Responsibility | Knows about MCP? |
|---|---|---|
| MCP tools | Tool definitions, argument coercion, error shaping | yes |
| CatalogService | Validation, version assignment, integrity, search orchestration | no |
| Repository | SQLite reads and writes, transaction boundary | no |

Domain logic sits below the protocol. PRD §9 notes that if assistant access "isn't available, the access model changes" — keeping the boundary in code means a different front end is an adapter swap, not a rewrite. It is also why a thin CLI over `CatalogService` costs almost nothing; PRD §7 permits a human interface so long as it is "not only" one.

## 4. Data model

One SQLite file. File bytes live in the database rather than on disk, so a publish is a single transaction (see §6.1).

```sql
CREATE TABLE skills (
  name       TEXT PRIMARY KEY,          -- lowercase slug; the only identity
  created_at TEXT NOT NULL
);

CREATE TABLE versions (
  skill_name   TEXT    NOT NULL REFERENCES skills(name),
  version      INTEGER NOT NULL,
  description  TEXT    NOT NULL,  -- projected from SKILL.md frontmatter, for listing
  publisher    TEXT,                    -- recorded, unverified; no auth in Phase 1
  published_at TEXT    NOT NULL,
  content_hash TEXT    NOT NULL,        -- sha256 over the whole bundle
  PRIMARY KEY (skill_name, version)
);

CREATE TABLE version_files (
  skill_name TEXT    NOT NULL,
  version    INTEGER NOT NULL,
  path       TEXT    NOT NULL,          -- relative to the skill directory
  content    BLOB    NOT NULL,          -- exact bytes, never normalized
  sha256     TEXT    NOT NULL,
  PRIMARY KEY (skill_name, version, path),
  FOREIGN KEY (skill_name, version) REFERENCES versions(skill_name, version)
);

CREATE VIRTUAL TABLE skills_fts USING fts5(name, description);
```

Three points worth defending:

**There is no `latest_version` column.** Latest is derived with `MAX(version) WHERE skill_name = ?`, a reverse scan on an existing primary key index. A stored pointer would be a second source of truth that can drift from the `versions` table — an odd thing to carry in a system whose selling point is that nothing drifts silently.

**File contents are stored inline, one row per file per version.** A content-addressed blob table was considered — it would store an unchanged template once across republishes and map neatly onto S3 keys later — and rejected for simplicity. Skills are small text files, so the duplication is cheap, and four tables beat five. The per-file `sha256` is kept because the integrity check in §6.2 needs it.

**Nothing issues an `UPDATE`.** Every table is insert-only (4.5). The schema itself is the guarantee, not a convention.

## 5. Tool contracts

Four tools. The surface is deliberately small — every tool description is spent from the assistant's context budget on every conversation.

| Tool | Arguments | Returns | Requirements |
|---|---|---|---|
| `publish_skill` | `files: dict[path, content]` (must include `SKILL.md`), `publisher` (optional) | `{published, name, version, content_hash, file_count}` | 1.x, 4.1, 4.4 |
| `discover_skills` | `query`, `limit` (default 10) | `[{name, description, latest_version}]` | 2.x |
| `retrieve_skill` | `name`, `version` (optional, defaults to latest) | `{found, name, version, content_hash, files: dict[path, content]}` | 3.x, 4.3 |
| `list_skill_versions` | `name` | `[{version, published_at, publisher, content_hash}]` | 4.2 |

`discover_skills`, `retrieve_skill` and `list_skill_versions` are annotated read-only; `publish_skill` is the sole writer.

Tool descriptions are prompt text — they are what the model reads when deciding whether to call. They are written as deliberately as a system prompt, and the description for `discover_skills` states that an empty result means nothing matched, so the assistant reports that rather than improvising (2.4).

## 5b. Modules

```
src/skills_catalog/
  models.py      Pydantic types: SkillRef, SkillBundle, VersionInfo, PublishResult
  errors.py      IntegrityFailure, SkillNotFound — faults, not domain outcomes
  validation.py  validate_publish() -> raises ValidationError(field, message)
  hashing.py     file_sha256(), bundle_hash()
  repository.py  SqliteRepository: schema init, transaction boundary, queries
  search.py      SearchIndex protocol; Fts5Index, plus query sanitizing
                 (LikeIndex fallback is optional — T-22, only if time remains)
  service.py     CatalogService: publish, discover, retrieve, list_versions
  observability.py  Per-call duration logging
  server.py      MCPServer tool definitions (thin)
  cli.py         serve, seed
```

Sample skills live in `seed_data/` at the repository root rather than inside the package, so no package-data configuration is needed — the CLI reads them from disk.

`CatalogService` is constructed with a repository and a search index, both as protocols. That is the seam: swapping SQLite for DynamoDB, or FTS5 for OpenSearch, replaces an implementation without touching the service or the tools.

## 5c. Flows

**Publish**

1. Tool receives arguments; Pydantic coerces types.
2. `validate_publish` runs every check — `SKILL.md` present at the bundle root; its frontmatter parses; `name` and `description` present and non-empty; `name` is a slug; instruction body after the frontmatter non-empty; every path relative, traversal-free and unique after normalization; all contents decode as UTF-8; counts and sizes within caps. First failure raises `ValidationError` naming the field.
3. Hash each file; compute the bundle hash over the sorted list of `(path, sha256)` pairs (§6.2).
4. One transaction: insert the skill row if new; compute `version = COALESCE(MAX(version), 0) + 1` **inside** the transaction; insert the version row; insert one file row per file; replace the search index entry.
5. Return `published: true` with the assigned version and content hash.

A validation failure returns `published: false` with the offending field and **no version number** (§6.5). Nothing is written.

**Discover**

1. Sanitize the query for FTS5 — raw natural language contains characters FTS5 reads as operators, so it is quoted rather than passed through.
2. `MATCH` ordered by rank, capped limit.
3. For each hit, read the latest version's description.
4. Return thin refs: name, description, latest version. No bodies, no file contents (2.3).

Nothing matching returns an empty list, which is a success.

**Retrieve**

1. Resolve the version: explicit if given, otherwise `MAX(version)`.
2. Unknown skill, or unknown version of a known skill, returns `found: false` with a message distinguishing the two cases.
3. Load the version row and its files.
4. Recompute the bundle hash and compare with the stored one. A mismatch means corruption and raises — returning content known to be wrong would violate PRD §7 outright.
5. Return the stored bytes as a path-to-content map, unchanged.

Publish and retrieve speak the same shape, and the catalog never composes or rewrites content — it stores what the author sent and returns exactly that. Round-trip fidelity is therefore structural rather than something the implementation has to be careful about, which is the strongest available reading of PRD §7. The retrieving assistant writes the map to disk and the skill is installed, making FR-03's "ready to use" literal.

The alternative considered was taking `name`, `description` and `body` as arguments and rendering `SKILL.md` on the way out. Rejected: it introduces a rendering step, and any divergence between how the manifest was written and how it is re-composed means the installed bytes differ from the published ones.

**List versions**

Read all versions for the name in order, returning version number, timestamp, publisher, and content hash. Versions whose hash matches an earlier version are marked as identical — not merged or suppressed, just visible, which is what PRD §3's "history is retained and inspectable" asks for.

## 6. Mechanisms

### 6.1 Atomic publish (1.5, 4.4)

Validate everything first — the full list is in the publish flow (§5c) — then write in a single transaction covering the skill row, the version row, every file row, and the search index. On any validation failure nothing is written and the error names the offending field.

Storing file bytes as BLOBs is what makes this genuinely atomic. If files lived on the filesystem their writes would not join the SQL transaction, and a crash between the two would leave either orphaned files or rows pointing at files that do not exist. That would need temp-write-and-rename plus an orphan sweep to approximate what one transaction gives outright.

### 6.2 Integrity (3.2, PRD §7)

At publish, hash each file and compute a bundle hash over the sorted list of `(path, sha256)` pairs. Because the manifest is itself a file, the bundle hash covers everything the author sent with nothing left out and no separately-serialized metadata to keep in step. At retrieve, recompute and compare before returning; a mismatch is an error, not a warning.

Bytes are stored exactly as published. No line-ending translation, no re-encoding, no whitespace trimming. A skill published from Windows with CRLF must retrieve identically on Linux, and normalizing anywhere would both alter content and break the hash — PRD §7 calls this out as "no silent loss or alteration."

### 6.3 Versioning (4.x)

Versions are integers starting at 1. Publishing an existing name computes `COALESCE(MAX(version), 0) + 1` inside the transaction and inserts that row. No existing row is touched and there is no pointer to update — which is the point of having no `latest_version` column (§4). Retrieval defaults to the highest version; an explicit `version` pins an earlier one.

### 6.4 Discovery (2.x)

FTS5 over name and description, re-indexed for that skill on publish. The assistant turns natural language into a query; the catalog does lexical matching. Results are thin by design: name, description, and latest version only. Returning instruction bodies would flood the assistant's context on a multi-result query and degrade the very interaction PRD §7 asks to keep fast. Retrieval is where the full bundle is paid for.

Semantic search is the obvious upgrade and is deliberately deferred — an embedding call in the search path would spend the latency budget in PRD §7 and most of the four hours. See `phase-2.md`.

### 6.5 Error semantics (1.3, 2.4, 3.3)

Domain outcomes are returned as structured results. Only genuine faults — a database failure, a bug — surface as protocol errors.

| Outcome | Result | Signal |
|---|---|---|
| Discover, matches found | list of refs | non-empty list |
| Discover, nothing matches | empty list | `[]`, a success |
| Retrieve, found | full bundle | `found: true` |
| Retrieve, unknown skill or version | no partial fields | `found: false` plus a message |
| Publish, accepted | confirmation | `published: true` with the assigned version |
| Publish, rejected | rejection | `published: false`, offending field named, **no version number** |
| Retrieve, stored bytes fail their hash | protocol error | corruption, never a `found: false` |
| Database fault, bug | protocol error | genuine failure only |

Three reasons for this shape:

**"No" is an answer, not a failure.** Asking whether a skill exists has two valid answers. Marking the negative one as an error conflates "the catalog is broken" with "the catalog is working and told you the truth" — which also makes the event log in §6.6 unable to distinguish a degraded service from an ordinary miss.

**One envelope.** Every outcome is read the same way: a field on a successful result. The alternative — an empty list here, an error flag there — is more surface for a client to handle inconsistently.

**A rejected publish carries no version number.** That is the load-bearing detail. Even if the model skims past `published: false`, there is nothing in the result that can be reported as a success, and the message names the field at fault so a retry is informed rather than blind.

The contract is stated in each tool's description, which is prompt text the model reads before calling. Messages are written to be relayed verbatim.

**What this cannot guarantee.** FR-02 and FR-03 are phrased as assistant behaviour — "the assistant clearly says so." The catalog controls its own output, not the model's phrasing. This design makes the correct behaviour the path of least resistance; it cannot make it certain. Tests therefore assert on tool output, and `DEMO.md` carries the evidence for the assistant-facing half.

### 6.6 Observability

Each tool call logs its name, outcome and duration to stdout as a JSON line. Nothing richer.

The PRD does not ask for logging. It earns its place because Requirement 6 (PRD §7, Responsiveness) prescribes no threshold, so responsiveness is measured rather than asserted — and the duration log is what backs the figures reported in the README. Without it that requirement has no evidence at all.

Stdout rather than a table in the catalog: telemetry should not live inside the system it observes, and both EKS and Lambda collect stdout into CloudWatch unchanged. Richer events — argument shapes, agent handoffs, cost per call — are a Phase 2 item.

## 7. Runtime and packaging

Python with the official `mcp` SDK (2.x, where the server class is `MCPServer` — `FastMCP` in 1.x), streamable HTTP transport on `/mcp`, stdlib `sqlite3`, `pytest` for tests. Two direct dependencies.

Managed with `uv`, which installs its own pinned Python. The reviewer's OS and Python version are unknown, so the toolchain is pinned rather than assumed; a `venv` and `pip` path is documented for anyone already on 3.10+. No Docker: the service is one process and one file, so a container would add a volume-mounting failure mode to the very requirement (PRD §9) it would be meant to serve.

Cross-platform by construction: `pathlib` throughout, no hardcoded system paths, database location configurable with a sensible default.

## 8. Deliberately not built

Authentication (PRD §8), de-duplication (PRD §8), semantic search, delete or deprecate, a web UI, and any deployed infrastructure. `decisions.md` records the options considered and rejected.

## 9. Known risks

- **Name collisions.** Identity is the skill name and there is no auth, so two developers can unknowingly version each other's skill. Inherent to FR-04 plus PRD §8; namespacing is a Phase 2 item.
- **SQLite as the single writer.** Correct and fast for this scale, and the wrong choice past one node.
- **Lexical search misses synonyms.** A skill described as "release notes" will not match a query for "changelog." Accepted for Phase 1 and the top-ranked Phase 2 item.
