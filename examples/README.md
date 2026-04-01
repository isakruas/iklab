# Examples

Working examples of a custom tool and a custom skill for IKLab.

## Structure

```
examples/
├── .iklab/
│   ├── settings.json              # Project settings
│   └── skills/
│       └── code_review.md         # Skill: structured code review
└── tools/
    └── tool_git.py                # Tool: Git operations (status, diff, log, blame)
```

## Quick start

```bash
cd examples
iklab
```

IKLab will read `.iklab/settings.json`, discover the Git tools in `./tools`,
and load the Code Review skill from `.iklab/skills`. Ask the agent to
"review my changes" and it will use both automatically.

## Custom tool — `tools/tool_git.py`

Provides four read-only Git tools:

| Tool | Description |
|------|-------------|
| `GitStatus` | Working-tree status (staged, unstaged, untracked) |
| `GitDiff` | Line-level diff (optionally staged, optionally per-file) |
| `GitLog` | Recent commit history with decoration |
| `GitBlame` | Per-line authorship for a file range |

All tools are in the **context** category (read-only, auto-approved).

### Anatomy of a tool module

Every tool module needs two things:

1. **Functions** decorated with `@mcp.tool(name="ToolName")` that return `str`.
2. **`TOOL_METADATA`** list so the registry can discover and categorize them.

```python
from iklab.tools import mcp

@mcp.tool(name="MyTool")
def my_tool(arg: str) -> str:
    """Description shown to the model."""
    return f"Result: {arg}"

TOOL_METADATA = [
    {
        "name": "MyTool",
        "category": "context",        # "context" | "planning" | "execution"
        "description": "Description shown to the model.",
        "source_module": "tools.my_module",
    },
]
```

Categories:
- **context** — read-only, auto-approved
- **planning** — analysis, requires approval
- **execution** — writes/commands, requires approval

## Custom skill — `.iklab/skills/code_review.md`

A skill is a Markdown file with YAML front-matter that teaches the agent a
multi-step workflow. When the user says something that matches a trigger
(e.g. "review my changes"), the agent follows the skill's instructions and
uses its recommended tools.

### Anatomy of a skill file

```yaml
---
name: Code Review
triggers:
  - review
  - diff
recommended_tools:
  - GitDiff
  - Read
description: Short description shown in the system prompt.
---

Step-by-step instructions the agent follows when this skill is activated.
```

## Configuration — `.iklab/settings.json`

```json
{
  "tool_paths": ["./tools", "iklab.tools"],
  "skills_paths": [".iklab/skills"]
}
```

- **tool_paths** — directories or Python packages to scan for tool modules.
- **skills_paths** — directories to scan for `.md` skill files.

Both accept relative paths (resolved from the project root) or absolute paths.
Environment variables `IKLAB_TOOL_PATHS` and `IKLAB_SKILL_PATHS` (colon-separated)
can override or extend these.
