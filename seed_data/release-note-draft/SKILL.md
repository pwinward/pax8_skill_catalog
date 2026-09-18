---
name: release-note-draft
description: Drafts release notes from a set of merged pull requests, grouped by change type.
---

When asked to draft release notes:

1. Collect the pull requests merged since the last release tag.
2. Read `template.md` and use it as the structure for the output.
3. Sort each PR into Added, Changed, Fixed, or Removed, using its labels where
   present and its title where not.
4. Write one line per PR in the user's voice, not the PR title verbatim. Say what
   changed for someone using the software, not what the diff did.
5. Leave a section out entirely if nothing belongs in it. Do not write "None".

Ask for the release version if it was not given.
