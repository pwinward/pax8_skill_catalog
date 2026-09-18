# Phase 2 — What is worth building next

PRD §12 Q1 asks the builder what the most valuable additions are once the core loop
works, and §11 leaves Phase 2 open. This answers it. It is not an implementation: §11
scopes Phase 1 to FR-01 through FR-04, and building ahead of that would have come out
of Phase 1's quality.

**How this was arrived at.** Rather than reason from first principles, I looked at what
registries already operating at company scale actually track — AWS Agent Registry (GA
August 2026, part of Bedrock AgentCore), Google's Skill Registry, Anthropic's
enterprise Skills guidance — and at the published security audit of the public skill
ecosystem. They converge, which is the useful part: the same few fields and states keep
reappearing, and they are not the ones this PRD scopes.

The ordering inverts what I first assumed. Semantic search is the obvious functional
gap and I had it first; it belongs fifth. Discovery quality is the bottleneck only once
you can trust what discovery returns.

---

## 1. Lifecycle: ownership, deprecation, removal

**Add:** `owner` and `team` on a skill; a status per version — `draft`, `approved`,
`deprecated` — with retrieval resolving to the latest *approved* version rather than
simply the latest; and a path for withdrawing a skill entirely.

**Why ownership and status.** Today `latest` and `trusted` are the same thing. A
developer publishing an experiment immediately changes what every other developer's
assistant retrieves by default. Separating the two is what makes a catalog safe to
publish into casually, which is the behaviour the PRD wants to encourage. Every
registry surveyed has this; AWS's lifecycle runs `DRAFT → PENDING_APPROVAL →
APPROVED / REJECTED → DEPRECATED`.

**Why removal is separate, and harder.** Deprecation is a status — cheap, and
consistent with everything here, since the version stays put and simply stops being
what retrieval returns. Deletion is not. It contradicts the guarantee the rest of the
design is built on: §4 says prior versions are retained, §7 says no silent loss, and
there is no `UPDATE` or `DELETE` against a published version anywhere in the schema.

But the need is real and specific. A skill published with a live credential in it, or
one found to carry the kind of injected instruction described in item 2, has to
actually leave — deprecating it still serves the content to anyone who asks for that
version by number.

The shape I would propose: deprecation as the default and only ordinary path, with
removal as a distinct privileged operation that tombstones the version — the row and
its hash stay so the history remains legible and honest, the file contents go, and
retrieval reports the version as withdrawn rather than as never having existed.

**Worth noting the PRD never mentions any of this** — not deletion, not deprecation,
not retirement, and not in §8's list of deferred items either (`requirements.md`, gap
2). A skill that turns out to be wrong currently has no exit at all.

## 2. Trust signals on skill content

**Add:** scanning at publish for injection patterns and committed secrets, a review
status, and provenance recording who published and who reviewed.

**Why.** The item I would argue hardest for, because it is specific to skills rather
than to catalogs generally. **A skill body is loaded into another developer's assistant
as instructions it will act on.** That makes the catalog a distribution channel for
prompt injection, not only for code.

Not hypothetical. Snyk audited 3,984 skills from public registries in February 2026:
36.8% carried at least one security flaw, 13.4% a critical one, including documented
cases where a few lines of markdown in a `SKILL.md` instructed an agent to read SSH
keys and exfiltrate them.

PRD §8's "assume a trusted set of developers" is a sound P0 scoping decision and this
build honours it. It is also the assumption that stops holding the moment the catalog
becomes a platform — and unlike everything else here, authentication does not address
it. Auth establishes *who published*; it says nothing about *what the skill says*.

## 3. Authentication and namespacing

**Add:** authenticated publishing, a verified publisher, and names scoped to a team or
person.

**Why.** PRD §8 defers this deliberately and Phase 1 accepts the consequence
(`decisions.md` D-12): identity is the bare skill name, so any caller may publish a new
version of anyone's skill, and two teams choosing the same name silently version each
other's work. Tolerable among a handful of trusted developers; not at company scale.

It also has to land before items 1 and 2 mean anything. An owner field nobody verifies
and an approval nobody is accountable for are decoration. The schema leaves room:
`publisher` is already recorded, just unverified, and nothing in the design assumes a
flat namespace permanently.

## 4. Usage telemetry

**Add:** retrieval counts per skill and version, discovery queries that return nothing,
and failure rates.

**Why.** Three questions the catalog cannot currently answer: which skills are actually
used, which are stale, and what developers looked for and did not find. The last is the
most valuable — a log of unmatched queries is a backlog of skills worth writing,
produced for free by people already asking.

The foundation exists. Every tool call already logs its name, outcome and duration to
stdout (`design.md` §6.6), including `no_match` on discovery. Aggregating that is a
small step from where Phase 1 ends.

## 5. Richer discovery

**Add:** tags and applicability triggers first; semantic or hybrid search after.

**Why.** Search today is lexical, so a skill described as "release notes" does not
match a query for "changelog" (`design.md` §9). The most visible shortcoming in the
system, and the reason I originally ranked it first.

It belongs here because the cheaper half solves much of it. Tags and an explicit "use
this when…" field give the assistant better signal than embeddings recover from a
one-line description, and they cost a column each. Semantic search adds an embedding
model, an index to keep in step with the system of record, and latency in the path
PRD §7 asks to keep interactive — worth doing, after the fields that make results worth
ranking.

---

## Not ranked here

**Larger bundles.** An upload endpoint and download URLs would remove the token cost of
publishing and the text-only restriction (`README.md`, known limits). Worth doing when
a real skill hits the limit, not before.

## Sources

- AWS Agent Registry — lifecycle states, owner and lineage, custom metadata schemas,
  audit trails
- Google Skill Registry — mutable skill with immutable revisions, payload validation
- Anthropic Skills for enterprise — org-wide provisioning, Git-backed versioning,
  promotion after review
- Snyk, "ToxicSkills" audit of 3,984 public skills, February 2026
