from __future__ import annotations

"""Dynamic system prompt composition from kernel base + runtime context."""

from .models import AgentConfig
from .prompts import load
from .skill_registry import build_skill_registry
from .tool_pool import ToolPool


def build_system_prompt(
    cfg: AgentConfig,
    tool_pool: ToolPool,
    expert_protocol: str = "",
    history_summary: str = "",
) -> str:
    """Compose the full system prompt from separate sections.

    Sections
    --------
    1. Kernel base — loaded from ``prompts/system.txt``
    2. Available tools — rendered from the current ToolPool
    3. Active expert protocol — dynamic persona/rules
    4. History summary — compacted transcript context
    5. Agent configuration hints
    """
    sections: list[str] = []

    # 1. Kernel base
    sections.append(load("system"))

    # 2. Available tools
    tool_section = tool_pool.as_markdown()
    if tool_section:
        sections.append(tool_section)

    # 2.5 Skill guidance: include matched skills (small snippets)
    try:
        skill_reg = build_skill_registry()
        # naive: include first 2 skills as guidance (could be improved by triggers)
        skill_snippets = []
        for s in list(skill_reg.skills)[:2]:
            snippet = f"<SKILL:{s.name}>\nDescription: {s.description}\nRecommended tools: {', '.join(s.recommended_tools)}\n{(s.body.splitlines()[0] if s.body else '')}\n</SKILL:{s.name}>"
            skill_snippets.append(snippet)
        if skill_snippets:
            sections.append("\n".join(skill_snippets))
    except Exception:
        # skill discovery is best-effort
        pass

    # 3. Active expert protocol
    if expert_protocol:
        sections.append(
            f"<ACTIVE_EXPERT_PROTOCOL>\n{expert_protocol}\n</ACTIVE_EXPERT_PROTOCOL>"
        )
    else:
        sections.append(
            "ACTIVE_EXPERT_PROTOCOL:\nNone. First, ORCHESTRATE a specialized protocol."
        )

    # 4. History summary
    if history_summary:
        sections.append(f"<HISTORY_SUMMARY>\n{history_summary}\n</HISTORY_SUMMARY>")

    # 5. Configuration hints
    config_hints = (
        f"Model: {cfg.model_name} | "
        f"Max retries: {cfg.max_validation_retries} | "
        f"Bash timeout: {cfg.max_bash_timeout}s"
    )
    sections.append(f"<CONFIG>\n{config_hints}\n</CONFIG>")

    # Final directive
    sections.append("CRITICAL: Use TOOLS, not text.")

    return "\n\n".join(sections)
