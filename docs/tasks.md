# Tasks — Skills Catalog

Ordered so that each checkpoint leaves a coherent, demonstrable system. Tests land with the code they cover, not as a final phase — if the four hours run out, whatever exists is proven rather than merely written.

Requirement IDs refer to `requirements.md`.

## Step 1 — Vertical slice: an assistant can round-trip a skill

| # | Task | Requirements |
|---|---|---|
| T-01 | Project skeleton: `pyproject.toml`, uv config, package layout, pytest config, `.gitignore`, README quickstart drafted | 7.1 |
| T-02 | Schema and `SqliteRepository`: table creation on startup, connection per operation, WAL, `foreign_keys = ON` | 4.5 |
| T-03 | Manifest parsing and Pydantic models: `SKILL.md` frontmatter to name, description, instruction body | 1.3 |
| T-04 | `CatalogService.publish` happy path, all writes in one transaction | 1.1, 1.2 |
| T-05 | `CatalogService.retrieve` for the latest version | 3.1 |
| T-06 | MCP server over streamable HTTP with `publish_skill` and `retrieve_skill`; manual smoke test from a client | 5.1 |

**Checkpoint 1** — a skill published from an assistant comes back intact.

## Step 2 — Validation and integrity

| # | Task | Requirements |
|---|---|---|
| T-07 | `validate_publish`: manifest present and parseable, required fields non-empty, name is a slug, paths relative and unique, UTF-8 only, size and count caps. Raises `ValidationError(field, message)` | 1.3, 1.4 |
| T-08 | Atomicity: a rejected publish writes nothing — no skill, version, file, or index row | 1.5 |
| T-09 | Per-file and bundle hashing; verify on retrieve, raise on mismatch | 3.2 |
| T-10 | Structured error results: rejected publish carries no version number; not-found is explicit | 1.3, 3.3 |

**Checkpoint 2** — FR-01 complete, PRD §7 consistency provable.

## Step 3 — Discovery

| # | Task | Requirements |
|---|---|---|
| T-11 | FTS5 index maintained on publish; query sanitizing so natural language cannot produce an FTS syntax error | 2.1 |
| T-12 | `discover_skills` tool: thin results, capped limit, empty list when nothing matches | 2.1, 2.2, 2.3, 2.4 |

**Checkpoint 3** — the reuse loop works end to end (PRD §3, goal 1).

## Step 4 — Versioning

| # | Task | Requirements |
|---|---|---|
| T-13 | Republish assigns N+1 computed inside the transaction; prior versions retained | 4.1 |
| T-14 | Retrieve a pinned version; unknown version reported distinctly from unknown skill | 3.4, 4.3 |
| T-15 | `list_skill_versions` tool, marking versions whose hash matches an earlier one | 4.2 |
| T-16 | Malformed republish rejected with existing versions untouched | 4.4 |

**Checkpoint 4 — PRD-complete.** FR-01 through FR-04 all satisfied.

## Step 5 — Evidence

| # | Task | Requirements |
|---|---|---|
| T-17 | `seed` command and three sample skills, including the PRD's `release-note-draft` | — |
| T-18 | Per-call duration logging to stdout | 6.1 |
| T-19 | Two-client integration test, plus `DEMO.md` captured from a real two-session run | 1.6, 5.1 |
| T-20 | README: quickstart, tool list, known limits, measured latency, AI-usage note | 6.1, 7.1 |
| T-21 | `decisions.md`, `phase-2.md` | PRD §12 Q1 |

**Checkpoint 5** — submittable.

## Step 6 — Only if time remains

| # | Task | Why it is last |
|---|---|---|
| T-22 | FTS5 availability check with `LIKE` fallback | Insures against an unknown reviewer environment; not required by the PRD |
| T-23 | GitHub Actions running the suite on Ubuntu | The only independent evidence the quickstart works off this machine |

## Deliberately not tasks

Concurrency testing, latency assertions, content-addressed blob dedupe, tar or zip upload, authentication, de-duplication, delete or deprecate. Each is recorded in `decisions.md` with the reason.
