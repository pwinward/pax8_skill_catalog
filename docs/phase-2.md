# Phase 2 — What is worth building next

PRD §12 Q1 asks the builder what the most valuable additions are once the core loop
works, and §11 leaves Phase 2 open. This is the answer, not an implementation: §11
scopes Phase 1 to FR-01 through FR-04, and building ahead of that would have come out
of Phase 1's quality.

**How this was arrived at.** Rather than reason from first principles, I looked at what
registries that already exist at company scale actually track — AWS Agent Registry
(GA August 2026, part of Bedrock AgentCore), Google's Skill Registry, and Anthropic's
enterprise Skills guidance — and at the one published security audit of the public
skill ecosystem. They converge, which is the useful part: the same handful of fields
and states keep reappearing, and they are not the ones this PRD scopes.

The ordering below inverts what I first assumed. Semantic search is the obvious
functional gap and I had it first; it belongs fifth. Discovery quality is the
bottleneck only once you can trust what discovery returns.

---

## 1. Ownership and lifecycle

**Add:** `owner` and `team` on a skill; a status per version — `draft`, `approved`,
`deprecated` — and retrieval that resolves to the latest *approved* version rather
than simply the latest.

**Why.** Today `latest` and `trusted` are the same thing, and they should not be.
A developer publishing an experiment immediately changes what every other developer's
assistant retrieves by default. Separating the two is what makes a catalog safe to
publish into casually, which is the behaviour the PRD wants to encourage.

It also closes a gap the PRD leaves open: nothing anywhere describes deleting,
deprecating or retiring a skill — not in the requirements, and not in §8's list of
deferred items either (see `requirements.md`, gap 2). A skill that turns out to be
wrong currently has no exit. Every registry surveyed has a deprecated state; AWS's
lifecycle is `DRAFT → PENDING_APPROVAL → APPROVED / REJECTED → DEPRECATED`.

Cheapest item here and the highest leverage: three columns and a resolution rule.

## 2. Trust signals on skill content

**Add:** scanning at publish for injection patterns and committed secrets, a review
status, and provenance for who published and who reviewed.

**Why.** This is the item I would argue hardest for, because it is specific to skills
rather than to catalogs generally. **A skill body is loaded into another developer's
assistant as instructions it will act on.** That makes the catalog a distribution
channel for prompt injection, not only for code.

It is not hypothetical. Snyk audited 3,984 skills from public registries in February
2026: 36.8% carried at least one security flaw and 13.4% a critical one, including
documented cases where a few lines of markdown in a `SKILL.md` instructed an agent to
read SSH keys and exfiltrate them.

PRD §8's "assume a trusted set of developers" is a sound P0 scoping decision and this
build honours it. It is also the assumption that stops holding the moment the catalog
becomes a platform — and unlike the other items here, authentication does not address
it. Auth establishes *who published*; it says nothing about *what the skill says*.

## 3. Authentication and namespacing

**Add:** authenticated publishing, a verified publisher, and names scoped to a team or
person.

**Why.** PRD §8 defers this deliberately, and Phase 1 accepts the consequence
(`decisions.md` D-13): identity is the bare skill name, so any caller may publish a new
version of anyone's skill, and two teams choosing the same name silently version each
other's work. That is tolerable among a handful of trusted developers and is not
tolerable at company scale.

It also has to land before items 1 and 2 mean anything. An owner field nobody verifies
and an approval nobody is accountable for are decoration. The schema already leaves
room: `publisher` is recorded but unverified, and nothing about the design assumes a
flat namespace permanently.

## 4. Usage telemetry

**Add:** retrieval counts per skill and per version, discovery queries that return
nothing, and failure rates.

**Why.** Three questions the catalog cannot currently answer: which skills are actually
being used, which are stale, and what developers looked for and did not find. The last
one is the most valuable — a log of unmatched queries is a backlog of skills worth
writing, produced for free by people already asking.

The foundation exists. Every tool call already logs its name, outcome and duration to
stdout (`design.md` §6.6), including `no_match` on discovery. Aggregating that is a
small step from where Phase 1 ends.

## 5. Richer discovery

**Add:** tags and applicability triggers first; semantic or hybrid search after.

**Why.** Search today is lexical, so a skill described as "release notes" does not
match a query for "changelog" (`design.md` §9). That is the most visible shortcoming in
the system and the reason I originally ranked it first.

It belongs here because the cheaper half solves much of it. Tags and an explicit "use
this when…" field give the assistant far better signal than embeddings recover from a
one-line description, and they cost a column each. Semantic search adds an embedding
model, an index to keep in step with the system of record, and latency in the path
PRD §7 asks to keep interactive — worth doing, but after the fields that make results
worth ranking.

---

## Deliberately not ranked highly

**De-duplication** (PRD §8) — real registries do treat it as core rather than a
refinement; AWS Agent Registry performs de-duplication analysis to surface redundant
capabilities. It is listed low here because it is a symptom: with owners, tags and
usage data in place, duplicates are visible without a detection mechanism.

**Larger bundles** — an upload endpoint and download URLs would remove the token cost
of publishing and the text-only restriction (`README.md`, known limits). Worth doing
when a real skill hits the limit, not before.

## Sources

- AWS Agent Registry — lifecycle states, owner and lineage, custom metadata schemas,
  de-duplication analysis, CloudTrail audit trails
- Google Skill Registry — mutable skill with immutable revisions, payload validation
- Anthropic Skills for enterprise — org-wide provisioning, Git-backed versioning,
  promotion after review
- Snyk, "ToxicSkills" audit of 3,984 public skills, February 2026
