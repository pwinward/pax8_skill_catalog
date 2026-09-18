# Requirements Document — Skills Catalog

## Introduction

The Skills Catalog is a shared store for reusable AI-assistant skills. Today a skill lives only on its author's machine, so sharing it means handing over a copy that immediately drifts out of sync. This system lets one developer publish a skill once and another developer's assistant discover and retrieve it, with every version retained.

Source: Skills Catalog PRD v0.1.0 (owner: Glenn Weigold). Scope: Phase 1 / MVP (P0) — FR-01 through FR-04. Terms used here are defined in PRD §4.

Acceptance criteria are written in EARS notation. Each cites the PRD clause it derives from and the test that proves it.

## Assumptions

1. The catalog is a shared service that multiple assistants connect to, not a store embedded in each developer's assistant. A per-developer store would satisfy the functional requirements while reproducing the problem in PRD §1.
2. A skill is a manifest plus optional supporting files (PRD §9). The manifest is `SKILL.md`, carrying `name` and `description` in frontmatter and the instruction body below it.
3. Skill files are UTF-8 text. Binary content is rejected rather than stored in a form that cannot be returned unchanged.
4. Developers are trusted; there is no authentication (PRD §8). A publisher is recorded but unverified.
5. The system runs locally and self-contained. No deployed infrastructure is part of the deliverable.

## Requirements

### Requirement 1 — Publish a skill

**User story:** As Developer 1, I want to publish my skill to the catalog, so that another developer can reuse it without me handing over files.
**Source:** FR-01, UC-01

| # | Acceptance criterion | Test |
|---|---|---|
| 1.1 | WHEN a developer publishes a bundle containing a valid `SKILL.md` THEN the catalog SHALL store it and return the assigned version | `test_publish_stores_and_confirms` |
| 1.2 | WHEN a bundle includes supporting files THEN the catalog SHALL store every file and return them complete on retrieval | `test_publish_round_trips_supporting_files` |
| 1.3 | IF `SKILL.md` is absent, unparseable, or missing a name, description or instruction body THEN the catalog SHALL reject the publish with an explanation naming the fault | `test_publish_rejects_missing_fields` |
| 1.4 | IF any file path is absolute, escapes the bundle root, or duplicates another after normalization, or IF any content is not UTF-8 text THEN the catalog SHALL reject the publish with an explanation | `test_publish_rejects_unsafe_paths`, `test_publish_rejects_binary_content` |
| 1.5 | WHEN a publish is rejected THEN the catalog SHALL store nothing — no skill, version, file or index entry | `test_rejected_publish_is_atomic` |
| 1.6 | WHEN a skill is published through one client session THEN it SHALL be discoverable and retrievable through a different client session against the same catalog | `test_two_clients_share_catalog`, `DEMO.md` |

### Requirement 2 — Discover skills through an AI assistant

**User story:** As Developer 2, I want to ask my AI assistant what skills exist for a need, so that I can reuse one instead of writing my own.
**Source:** FR-02, UC-02

| # | Acceptance criterion | Test |
|---|---|---|
| 2.1 | WHEN a developer describes a need in natural language through an assistant THEN the catalog SHALL return the published skills that match | `test_discover_returns_matches` |
| 2.2 | WHEN discovery returns results THEN each result SHALL carry at least the skill name and description | `test_discover_returns_name_and_description` |
| 2.3 | WHEN discovery returns results THEN no result SHALL carry an instruction body or file contents | `test_discover_results_are_thin` |
| 2.4 | IF nothing matches THEN the catalog SHALL return an explicit empty result, not an error and not a near match | `test_discover_no_match_returns_empty` |

### Requirement 3 — Retrieve a skill through an AI assistant

**User story:** As Developer 2, I want my AI assistant to retrieve a published skill, so that I get the same one Developer 1 has, ready to use.
**Source:** FR-03, UC-03

| # | Acceptance criterion | Test |
|---|---|---|
| 3.1 | WHEN a developer requests a named skill THEN the catalog SHALL return the latest version complete — manifest and every supporting file | `test_retrieve_returns_latest_complete` |
| 3.2 | WHEN a skill is retrieved THEN the returned bytes SHALL be identical to those published, verified by content hash, with no line-ending or encoding normalization | `test_retrieve_is_byte_identical` |
| 3.3 | IF the named skill does not exist THEN the catalog SHALL return an explicit not-found | `test_retrieve_unknown_returns_not_found` |
| 3.4 | IF the skill exists but the requested version does not THEN the catalog SHALL report that distinctly from an unknown skill | `test_retrieve_unknown_version` |

### Requirement 4 — Version a skill

**User story:** As Developer 1, I want publishing an updated skill to create a new version, so that changes are tracked and nothing is silently overwritten.
**Source:** FR-04, UC-04

| # | Acceptance criterion | Test |
|---|---|---|
| 4.1 | WHEN a developer publishes under an existing name THEN the catalog SHALL create version N+1 and retain all prior versions | `test_republish_creates_new_version` |
| 4.2 | WHEN a developer requests a skill's history THEN the catalog SHALL return each version's number, timestamp, publisher and content hash | `test_list_versions` |
| 4.3 | WHEN a skill is retrieved without a version THEN the catalog SHALL return the latest, and WHEN a version is named THEN it SHALL return that version complete | `test_retrieve_pinned_version` |
| 4.4 | IF a re-publish is malformed THEN the catalog SHALL reject it and leave existing versions untouched | `test_malformed_republish_leaves_versions_intact` |
| 4.5 | The catalog SHALL expose no operation that mutates a published version | Schema and service carry no UPDATE or DELETE against a published version; shown by `test_republish_creates_new_version` and `test_retrieve_pinned_version` |

### Requirement 5 — Assistant-mediated access

**Source:** PRD §7 (Assistant-mediated access), D1

| # | Acceptance criterion | Evidence |
|---|---|---|
| 5.1 | WHEN a developer discovers or retrieves a skill THEN it SHALL be possible through an AI assistant acting on natural-language intent, not only through a human-operated interface | `test_end_to_end_via_mcp_client`, `DEMO.md` |

### Requirement 6 — Responsiveness

**Source:** PRD §7 (Responsiveness). No numeric SLO is prescribed; none is invented.

| # | Acceptance criterion | Evidence |
|---|---|---|
| 6.1 | WHEN a tool call completes THEN the catalog SHALL log its duration, and the measured figures from the demo run SHALL be reported in the README | Duration log, README |

### Requirement 7 — Self-contained operation

**Source:** PRD §9 (Constraints)

| # | Acceptance criterion | Evidence |
|---|---|---|
| 7.1 | WHEN a reviewer clones the repository THEN they SHALL be able to start the catalog and run the demo from the README, on any operating system, without cloud credentials | Manual verification from a clean clone |

## Out of scope

Recorded, not built. Rationale for each is in `decisions.md`.

- Authentication and access control (PRD §8)
- De-duplication of similar skills (PRD §8)
- Delete, deprecate, or yank — see gap 2
- Semantic or embedding-based search — see `phase-2.md`
- PRD §12 Q1 is answered in writing, not implemented (§11 scopes Phase 1 to FR-01..FR-04)

## Gaps found in the PRD

1. **FR-04 AC2 has no use case.** UC-04 covers publishing a new version, but nothing covers *seeing* history, which FR-04 requires. Resolved by adding a `list_skill_versions` tool.
2. **Delete and deprecate appear nowhere** — not in the requirements, and not in §8's deferred list either. An omission rather than a decision. Not built; flagged so it is visible.
3. **Name is the only identity.** FR-04 keys versioning on name alone and §8 removes authentication, so any caller may publish a new version of anyone's skill. Accepted for Phase 1; recorded in `decisions.md`.
4. **No numeric SLO.** §7 leaves latency to the builder, so Requirement 6 measures and reports rather than asserting a threshold.

## Definition of done

1. Every acceptance criterion in Requirements 1 through 4 has a passing test.
2. Requirement 5 is evidenced by a `DEMO.md` transcript from two client sessions against one catalog.
3. The README quickstart has been run from a clean clone.
4. `decisions.md`, `phase-2.md` and `production.md` exist.
