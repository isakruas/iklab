---
name: summarize
description: Summarize long conversation context to reduce token usage and keep focus on the current task.
triggers:
  - conversation is too long
  - messages are getting long
  - context is too large
  - summarize the conversation
  - compact messages
recommended_tools:
  - Think
  - Read
---

# Summarization Skill

When the conversation history becomes too long or verbose, use this skill to produce a concise summary that preserves essential context.

## When to Activate

- The conversation has accumulated many tool outputs and intermediate steps.
- You notice repeated context or redundant information in the history.
- The user explicitly asks you to summarize or shorten the conversation.

## Procedure

1. Use [Think] to identify the key facts from the conversation so far:
   - What is the user's original task/goal?
   - What files were created, modified, or read?
   - What decisions were made and why?
   - What is the current state of progress?
   - What are the remaining steps?

2. Produce a structured summary in this format:

```
TASK: <one-line description of the user's goal>
PROGRESS:
- <completed step 1>
- <completed step 2>
FILES CHANGED:
- <path>: <what changed>
DECISIONS:
- <key decision and rationale>
REMAINING:
- <next step 1>
- <next step 2>
```

3. Present the summary to the user and continue working from the summarized context.

## Rules

- Keep the summary under 300 words.
- Focus on FACTS and ACTIONS, not on tool output details.
- Preserve file paths, variable names, and technical specifics.
- Drop intermediate errors that were already resolved.
- Drop verbose tool outputs (file contents, shell output) — reference by path instead.
