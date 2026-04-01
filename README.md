# IKLab

Planning-first CLI agent powered by Granite 4.0-H-Tiny via Docker Model Runner.

## Quick Start

```bash
# 1. Start the model
docker model run ai/granite-4.0-h-tiny

# 2. Install
pip install -e .

# 3. Run
iklab                          # interactive mode
iklab "analyze this project"   # single command
```

## CLI Flags

```
iklab                                  interactive mode
iklab "task description"               single-task mode
iklab --simple-mode                    context-only tools (Read, Glob, Grep, ListDirectory)
iklab --deny-tool Bash                 block a specific tool (repeatable)
iklab --deny-prefix mcp_               block tools by prefix (repeatable)
iklab --max-turns 20                   limit conversation turns
iklab --session <ID>                   restore a previous session
iklab --history                        show session history on exit
iklab --yolo                           skip permission prompts (auto-approve all)
iklab --version                        show version
```

## Permission System

By default, IKLab asks for permission before executing tools that modify state:

```
  [Tool] Write(path='app.js', content='...')
  [Permission] Allow Write(path='app.js')? [yes / no / always]:
```

- **y** / **yes** — allow this one call
- **n** / **no** — deny (tool returns error to the model)
- **a** / **always** — allow this tool for the rest of the session

Context tools (`Read`, `ListDirectory`, `Glob`, `Grep`) are auto-approved.
Use `--yolo` to skip all prompts.

## Architecture

```
iklab/
  __init__.py              package root, version
  cli.py                   argparse entry point
  agent.py                 Agent class, chat loop, MCP client
  config.py                env-var config loader (IKLAB_*)
  models.py                dataclasses: AgentConfig, TurnResult, SessionInfo, UsageSummary
  model.py                 LLM interface (ask, chat)
  sandbox.py               filesystem sandbox (WORKDIR jail)
  ignore.py                .gitignore-style filtering
  permissions.py           ToolPermissionContext + ToolApprover
  tool_registry.py         ToolMeta + ToolRegistry (central tool index)
  tool_pool.py             ToolPool + assemble_tool_pool (filtering by mode/phase/perms)
  prompt_builder.py        dynamic system prompt composition
  query_engine.py          budget/turn limits + compaction control
  bootstrap.py             initialization stage graph
  transcript.py            mutable conversation store
  cost_tracker.py          token usage tracker
  history.py               session event log
  session_store.py         JSON session persistence (.iklab/sessions/)
  server.py                MCP server entry point
  prompts/
    __init__.py            prompt loader
    system.txt             kernel system prompt
  tools/
    __init__.py            shared FastMCP instance
    context.py             ListDirectory, Read, Glob, Grep
    planning.py            AnalyzeProject, PlanTask
    execution.py           Write, Bash, Think, WebSearch
```

## Tools

### Context (read-only, auto-approved)

| Tool | Description |
|------|-------------|
| `ListDirectory` | List files/folders respecting ignore rules |
| `Read` | Read file content (binary-safe) |
| `Glob` | Find files by glob pattern |
| `Grep` | Search text inside files |

### Planning (requires approval)

| Tool | Description |
|------|-------------|
| `AnalyzeProject` | Deep project analysis (structure, stack, architecture) |
| `PlanTask` | Step-by-step execution plan |

### Execution (requires approval)

| Tool | Description |
|------|-------------|
| `Write` | Create or overwrite a file |
| `Bash` | Execute a shell command (sandboxed) |
| `Think` | Reason about a problem (LLM call) |
| `WebSearch` | Search the internet via DuckDuckGo |

## Custom Tools

You can add custom tools by creating a new module in `iklab/tools/` and registering them.
See `examples/` for templates.

## Configuration

| Env var | Default | Description |
|---------|---------|-------------|
| `IKLAB_MODEL_URL` | `http://localhost:12434/v1/chat/completions` | Model endpoint |
| `IKLAB_MODEL_NAME` | `ai/granite-4.0-h-tiny` | Model name |
| `IKLAB_MODEL_TIMEOUT` | `120` | Timeout in seconds |
| `IKLAB_MAX_RETRIES` | `3` | Max validation retries |

## Tests

```bash
python -m pytest tests/ -v
```
