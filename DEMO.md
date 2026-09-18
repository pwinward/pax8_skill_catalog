# Demo — one catalog, two developers

Captured from a real run against a running catalog. Two independent client sessions
connect to the same service; nothing is shared between them but the catalog itself.
Server log lines are the catalog's own output, unedited.

```
$ uv run skills-catalog --db catalog.db seed
published k8s-pod-triage v1 (2 files)
published pr-description v1 (1 files)
published release-note-draft v1 (2 files)

$ uv run skills-catalog --db catalog.db serve
skills-catalog listening on http://127.0.0.1:8000/mcp (db: catalog.db)
```

## Developer 1 publishes a skill

Their assistant reads the skill directory and calls `publish_skill`.

```
publish_skill(files={"SKILL.md": ..., "format.md": ...}, publisher="developer-1")

{
  "published": true,
  "name": "incident-timeline",
  "version": 1,
  "content_hash": "cfaf093d62a0d3e29affe60e5b863673ec2a9c8663a4e208d31cd208c48e33e5",
  "file_count": 2
}
```

## Developer 2 finds it, in a separate session

They have not spoken to Developer 1 and do not know the skill's name.

```
discover_skills(query="is there anything for reconstructing what happened during an incident?")

[
  {
    "name": "incident-timeline",
    "description": "Builds a timeline of an incident from logs, alerts and chat history.",
    "latest_version": 1
  }
]
```

The query is a plain question, punctuation and all. FTS5 would read much of it as
syntax, so the catalog tokenizes it before matching (see `design.md` §6.4).

```
retrieve_skill(name="incident-timeline")

found=True  version=1  files=['SKILL.md', 'format.md']
content_hash: cfaf093d62a0d3e29affe60e5b863673ec2a9c8663a4e208d31cd208c48e33e5
```

The hash matches what Developer 1 published. The files map is what the assistant
writes to disk — at which point the skill is installed and usable.

## Nothing matches, and nothing is there

Both are ordinary answers, not errors. `is_error` is false in both cases, so the
assistant relays them rather than treating the call as failed.

```
discover_skills(query="quantum chromodynamics simulation")
[]                                                          is_error: False

retrieve_skill(name="does-not-exist")
"No skill named 'does-not-exist'."                          is_error: False
```

## Developer 1 publishes an update

```
publish_skill(files={...})        -> published v2, hash eb3a3aa2...

list_skill_versions(name="incident-timeline")
[
  {"version": 1, "published_at": "2026-09-18T22:52:00+00:00",
   "publisher": "developer-1", "content_hash": "cfaf093d...", "identical_to": null},
  {"version": 2, "published_at": "2026-09-18T22:52:00+00:00",
   "publisher": "developer-1", "content_hash": "eb3a3aa2...", "identical_to": null}
]

retrieve_skill(name="incident-timeline", version=1)   -> version 1, still intact
```

## A malformed publish changes nothing

```
publish_skill(files={"SKILL.md": "---\nname: incident-timeline\n---\n\nNo description.\n"})

{
  "published": false,
  "field": "description",
  "message": "SKILL.md frontmatter is missing 'description'.",
  "version": null
}

list_skill_versions(name="incident-timeline")  ->  [1, 2]
```

The rejection names the field at fault and carries **no version number**, so there is
nothing in it an assistant could relay as a success. Both existing versions are
untouched.

## What the catalog logged

Unedited stdout from the run above.

```json
{"tool": "publish_skill", "file_count": 2, "outcome": "published", "skill": "incident-timeline", "version": 1, "duration_ms": 1.39}
{"tool": "discover_skills", "outcome": "matched", "result_count": 1, "duration_ms": 0.68}
{"tool": "retrieve_skill", "skill": "incident-timeline", "outcome": "found", "version": 1, "duration_ms": 1.11}
{"tool": "discover_skills", "outcome": "no_match", "result_count": 0, "duration_ms": 0.48}
{"tool": "retrieve_skill", "skill": "does-not-exist", "outcome": "not_found", "version": null, "duration_ms": 0.36}
{"tool": "publish_skill", "file_count": 2, "outcome": "published", "skill": "incident-timeline", "version": 2, "duration_ms": 0.79}
{"tool": "list_skill_versions", "skill": "incident-timeline", "outcome": "found", "version_count": 2, "duration_ms": 0.34}
{"tool": "retrieve_skill", "skill": "incident-timeline", "outcome": "found", "version": 1, "duration_ms": 0.69}
{"tool": "publish_skill", "file_count": 1, "outcome": "rejected", "skill": null, "version": null, "duration_ms": 0.01}
{"tool": "list_skill_versions", "skill": "incident-timeline", "outcome": "found", "version_count": 2, "duration_ms": 0.3}
```

Ten calls, median 0.68 ms, slowest 1.39 ms. PRD §7 asks for discovery and retrieval to
feel interactive inside an assistant conversation and prescribes no threshold, so the
figure is measured and reported rather than asserted in a test.
