# Demo — one catalog, two developers

Captured from a real run. Every response below is the catalog's actual output, and the
log at the end is its unedited stdout.

Two developers, each with their own AI assistant, connected to one running catalog.
Neither talks to the other.

```
$ uv run skills-catalog seed
published k8s-pod-triage v1 (2 files)
published pr-description v1 (1 files)
published release-note-draft v1 (2 files)

$ uv run skills-catalog serve
skills-catalog listening on http://127.0.0.1:8000/mcp (db: catalog.db)
```

---

## 1. Developer 2 looks for something that does not exist yet

They ask their assistant whether anyone has written a skill for reconstructing an
incident. The assistant searches the catalog.

```
discover_skills(query="is there anything for reconstructing what happened during an incident?")
→ []
```

An empty list, not an error. The assistant tells them nothing matches, rather than
offering something close.

## 2. Developer 1 publishes one

Their assistant reads the skill directory from disk and publishes it.

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

No file was sent to anyone, and no repository was shared.

## 3. Developer 2 asks again, in a separate session

Same question as step 1. Nothing about their setup changed.

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
search syntax, so the catalog breaks it into terms before matching (`design.md` §6.4).

```
retrieve_skill(name="incident-timeline")

{
  "found": true,
  "version": 1,
  "content_hash": "cfaf093d62a0d3e29affe60e5b863673ec2a9c8663a4e208d31cd208c48e33e5",
  "files": ["SKILL.md", "format.md"]
}

bytes identical to what was published: True
```

The hash matches step 2. The files map is what the assistant writes to disk, at which
point the skill is installed and usable.

## 4. The seeded skills are found the same way

Nothing special about a skill published through the API versus one loaded at startup.

```
discover_skills(query="my kubernetes pod keeps crashing")

[
  {
    "name": "k8s-pod-triage",
    "description": "Diagnoses a failing Kubernetes pod by working outward from its status.",
    "latest_version": 1
  }
]
```

## 5. Asking for what is not there

Both are ordinary answers rather than failures — `is_error` is false in each case — so
the assistant relays them instead of treating the call as broken.

```
discover_skills(query="quantum chromodynamics simulation")
→ []                                              is_error: false

retrieve_skill(name="does-not-exist")
→ "No skill named 'does-not-exist'."              is_error: false
```

## 6. Developer 1 publishes an update

```
publish_skill(files={...})

{"published": true, "name": "incident-timeline", "version": 2,
 "content_hash": "eb3a3aa24870e46857a68d8eed26ee3ea65e6376c18f0a7d44f3a829b90a685e"}
```

Version 1 was not touched. The history shows both:

```
list_skill_versions(name="incident-timeline")

[
  {"version": 1, "published_at": "2026-09-18T23:44:31+00:00",
   "publisher": "developer-1", "content_hash": "cfaf093d...", "identical_to": null},
  {"version": 2, "published_at": "2026-09-18T23:44:31+00:00",
   "publisher": "developer-1", "content_hash": "eb3a3aa2...", "identical_to": null}
]

retrieve_skill(name="incident-timeline", version=1)
→ version 1, content_hash cfaf093d...   (the hash from step 2, unchanged)
```

## 7. A malformed publish changes nothing

```
publish_skill(files={"SKILL.md": "---\nname: incident-timeline\n---\n\nNo description.\n"})

{
  "published": false,
  "field": "description",
  "message": "SKILL.md frontmatter is missing 'description'.",
  "version": null,
  "content_hash": null
}

list_skill_versions(name="incident-timeline")  →  versions [1, 2]
```

The rejection names the field at fault and carries **no version number**, so there is
nothing in it an assistant could relay as a success. Both versions are untouched.

## 8. The catalog is stopped and restarted

A different process, on a different port, against the same database file.

```
$ ^C
$ uv run skills-catalog serve --port 8963

list_skill_versions(name="incident-timeline")
[
  {"version": 1, "publisher": "developer-1", "content_hash": "cfaf093d62a0d3e2..."},
  {"version": 2, "publisher": "developer-1", "content_hash": "eb3a3aa24870e468..."}
]

retrieve_skill(name="incident-timeline", version=1)
{"found": true, "version": 1, "content_hash": "cfaf093d62a0d3e2...",
 "files": ["SKILL.md", "format.md"]}
```

Same hashes as step 2, published by a process that no longer exists. The catalog is a
place skills live, not a cache in front of one.

---

## What the catalog logged

Unedited stdout from the session above.

```json
{"tool": "discover_skills", "outcome": "no_match", "result_count": 0, "duration_ms": 0.93}
{"tool": "publish_skill", "file_count": 2, "outcome": "published", "skill": "incident-timeline", "version": 1, "duration_ms": 0.95}
{"tool": "discover_skills", "outcome": "matched", "result_count": 1, "duration_ms": 0.46}
{"tool": "retrieve_skill", "skill": "incident-timeline", "outcome": "found", "version": 1, "duration_ms": 0.78}
{"tool": "discover_skills", "outcome": "no_match", "result_count": 0, "duration_ms": 0.41}
{"tool": "retrieve_skill", "skill": "does-not-exist", "outcome": "not_found", "version": null, "duration_ms": 0.32}
{"tool": "publish_skill", "file_count": 2, "outcome": "published", "skill": "incident-timeline", "version": 2, "duration_ms": 0.72}
{"tool": "list_skill_versions", "skill": "incident-timeline", "outcome": "found", "version_count": 2, "duration_ms": 0.41}
{"tool": "retrieve_skill", "skill": "incident-timeline", "outcome": "found", "version": 1, "duration_ms": 0.63}
{"tool": "publish_skill", "file_count": 1, "outcome": "rejected", "skill": null, "version": null, "duration_ms": 0.01}
{"tool": "list_skill_versions", "skill": "incident-timeline", "outcome": "found", "version_count": 2, "duration_ms": 0.65}
{"tool": "discover_skills", "outcome": "matched", "result_count": 1, "duration_ms": 0.48}
```

Twelve calls, median 0.63 ms, slowest 0.95 ms. PRD §7 asks for discovery and retrieval
to feel interactive inside an assistant conversation and prescribes no threshold, so the
figure is measured and reported rather than asserted in a test.
