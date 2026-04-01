---
name: Example Project Analysis
triggers:
  - analyze
  - audit
recommended_tools:
  - ListDirectory
  - Read
description: Guidance to analyze a repository and summarize top-level structure.
---

Use this skill when the user asks for an analysis of the project structure. Steps:

1. List top-level directories and files.
2. Read README, setup files, and top-level modules.
3. Use grep or glob to find tests and source directories.

Prefer non-destructive tools (ListDirectory, Read) before any modifications.
