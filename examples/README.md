# Examples

Custom tool templates for IKLab. Copy any of these into `iklab/tools/` and import in `iklab/server.py`.

## Available Examples

| File | Tools | Category |
|------|-------|----------|
| `tool_git.py` | `GitStatus`, `GitDiff`, `GitLog` | context |
| `tool_http.py` | `HttpGet`, `HttpPost` | execution |
| `tool_docker.py` | `DockerPs`, `DockerLogs`, `DockerImages` | context |
| `tool_database.py` | `SqlQuery`, `SqlTables` | context |

## How to Use

### 1. Copy the tool file

```bash
cp examples/tool_git.py iklab/tools/git.py
```

### 2. Register in server.py

Edit `iklab/server.py` and add the import:

```python
from .tools import context, planning, execution  # existing
from .tools import git  # noqa: F401  <-- add this
```

### 3. Add to registry (optional)

To include in the tool registry (for filtering/pool), edit `iklab/tool_registry.py`:

```python
def build_tool_registry() -> ToolRegistry:
    from .tools import context, planning, execution, git  # <-- add module

    all_meta: list[ToolMeta] = []
    for module in (context, planning, execution, git):  # <-- add to list
        ...
```

### 4. Reinstall and run

```bash
pip install -e .
iklab
```

## Writing Your Own Tool

Every tool module needs:

1. **Tool functions** decorated with `@mcp.tool(name="ToolName")`
2. **TOOL_METADATA** list with name, category, description, source_module

```python
from iklab.tools import mcp

@mcp.tool(name="MyTool")
def my_tool(arg: str) -> str:
    """Description shown to the model."""
    return f"Result: {arg}"

TOOL_METADATA = [
    {
        "name": "MyTool",
        "category": "execution",  # or "context", "planning"
        "description": "Description shown to the model.",
        "source_module": "tools.my_module",
    },
]
```

Categories:
- **context** — read-only, auto-approved (no permission prompt)
- **planning** — analysis/planning, requires approval
- **execution** — writes/commands, requires approval
