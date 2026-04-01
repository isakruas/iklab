from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentConfig:
    """Immutable agent configuration with env-var overrides."""

    model_url: str = "http://localhost:12434/v1/chat/completions"
    model_name: str = "ai/granite-4.0-h-tiny"
    model_timeout: int = 120
    max_validation_retries: int = 3
    max_bash_timeout: int = 60
    max_walk_files: int = 500
    max_search_results: int = 200
    max_read_bytes: int = 50_000
    # Tuple of import paths or filesystem paths to search for tool modules.
    # Examples: ("iklab.tools",) or ("./tools", "/home/user/mytools")
    tools_paths: tuple[str, ...] = ("iklab.tools",)
    # Optional list of external MCP server endpoints (URLs) to connect to.
    # Example: ("http://localhost:12434", "http://other:12434")
    mcp_servers: tuple[str, ...] = ()
    # Optional list of paths or packages to discover user-written skills (markdown files)
    skills_paths: tuple[str, ...] = (".iklab/skills",)
    plan_tools: frozenset[str] = frozenset({"ListDirectory", "Read", "Glob", "Grep"})
    verify_tools: frozenset[str] = frozenset({"ListDirectory", "Read", "Glob", "Grep"})
    blocked_commands: tuple[str, ...] = (
        "rm -rf /",
        "rm -rf /*",
        "mkfs",
        "dd if=",
        ":(){",
        "fork",
        "shutdown",
        "reboot",
        "poweroff",
        "chmod -R 777 /",
        "chown -R",
        "> /dev/sd",
        "curl | sh",
        "curl | bash",
        "wget | sh",
        "wget | bash",
    )


@dataclass(frozen=True)
class TurnResult:
    """Result of a single agent turn."""

    content: str = ""
    tool_calls: tuple[dict, ...] = ()
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str = ""


@dataclass(frozen=True)
class SessionInfo:
    """Metadata for a persistent session."""

    session_id: str = ""
    messages: tuple[dict, ...] = ()
    input_tokens: int = 0
    output_tokens: int = 0


@dataclass(frozen=True)
class UsageSummary:
    """Accumulated token usage."""

    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens
