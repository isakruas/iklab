---
name: Code Review
triggers:
  - review
  - code review
  - check changes
  - diff
  - pr
description: Walk through uncommitted changes and provide a structured code review with actionable feedback.
recommended_tools:
  - GitStatus
  - GitDiff
  - GitLog
  - Read
  - Grep
---

## When to activate

Use this skill whenever the user asks you to review code, check their changes,
prepare a pull request description, or audit recent modifications.

## Workflow

1. **Gather context** — Run `GitStatus` to see which files changed, then
   `GitLog` (5–10 commits) to understand recent direction.
2. **Read the diff** — Use `GitDiff` (staged and unstaged) to get the full
   picture. For large diffs, diff individual files one at a time.
3. **Inspect surrounding code** — For each changed file, `Read` the full file
   so you can evaluate the change in context (imports, sibling functions, tests).
4. **Cross-reference** — Use `Grep` to find other call sites or usages of any
   modified function/class to ensure nothing is broken.
5. **Deliver the review** — Organize feedback into sections:

   - **Summary**: one-paragraph overview of what changed and why.
   - **Correctness**: bugs, logic errors, edge cases.
   - **Security**: injection risks, secrets, permissions.
   - **Style**: naming, duplication, dead code.
   - **Suggestions**: optional improvements, not blockers.

## Guidelines

- Be specific: reference file names and line numbers.
- Distinguish blocking issues from nice-to-haves.
- If everything looks good, say so — don't invent problems.
- When unsure about intent, ask the user before assuming a bug.
