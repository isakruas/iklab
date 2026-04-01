from __future__ import annotations

from dataclasses import dataclass, field

# Tools that are always safe (read-only context)
AUTO_APPROVE_TOOLS = frozenset(
    {
        "List",
        "Read",
        "Glob",
        "Grep",
    }
)


@dataclass(frozen=True)
class ToolPermissionContext:
    """Immutable context that controls which tools are blocked."""

    deny_names: frozenset[str] = field(default_factory=frozenset)
    deny_prefixes: tuple[str, ...] = ()

    @classmethod
    def from_iterables(
        cls,
        deny_names: list[str] | None = None,
        deny_prefixes: list[str] | None = None,
    ) -> ToolPermissionContext:
        return cls(
            deny_names=frozenset(name.lower() for name in (deny_names or [])),
            deny_prefixes=tuple(prefix.lower() for prefix in (deny_prefixes or [])),
        )

    def blocks(self, tool_name: str) -> bool:
        """Return True if *tool_name* is denied by this context."""
        lowered = tool_name.lower()
        return lowered in self.deny_names or any(lowered.startswith(prefix) for prefix in self.deny_prefixes)


class ToolApprover:
    """Interactive gate that asks the user before executing non-safe tools.

    Approval options:
        y  — allow this one call
        n  — deny this call
        a  — always allow this tool for the rest of the session
    """

    def __init__(
        self,
        auto_approve: frozenset[str] | None = None,
        always_approve_all: bool = False,
    ):
        self._auto: frozenset[str] = auto_approve or AUTO_APPROVE_TOOLS
        self._session_approved: set[str] = set()
        self._always_approve_all = always_approve_all

    def approve(self, tool_name: str, args_summary: str) -> bool:
        """Return True if the tool call is allowed.

        Auto-approves read-only tools. For others, prompts the user.
        """
        if self._always_approve_all:
            return True
        if tool_name in self._auto or tool_name in self._session_approved:
            return True
        return self._prompt(tool_name, args_summary)

    def _prompt(self, tool_name: str, args_summary: str) -> bool:
        R = "\033[0m"
        Y = "\033[33m"
        B = "\033[1m"
        try:
            answer = (
                input(
                    f"  {Y}{B}[Permission]{R} Allow {B}{tool_name}{R}({args_summary})? "
                    f"[{B}y{R}es / {B}n{R}o / {B}a{R}lways]: "
                )
                .strip()
                .lower()
            )
        except (EOFError, KeyboardInterrupt):
            print()
            return False
        if answer in ("a", "always"):
            self._session_approved.add(tool_name)
            return True
        return answer in ("y", "yes", "")
