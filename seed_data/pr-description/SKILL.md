---
name: pr-description
description: Writes a pull request description from the diff and the branch history.
---

When asked to describe a pull request:

1. Read the diff in full, and the commit messages on the branch.
2. Open with one sentence saying what changes for a user of this code. Not
   "refactors the handler" — what is different now.
3. Explain why, where the diff does not make it obvious. Link the issue if there
   is one.
4. List anything a reviewer should look at closely: a decision that could have
   gone another way, a piece you are unsure about, a deliberate omission.
5. Say how it was verified. "Tests pass" is not how it was verified.

Do not summarize the diff file by file. The reviewer can read the diff.
