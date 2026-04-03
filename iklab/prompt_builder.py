"""Dynamic system prompt composition from kernel base + runtime context."""

from __future__ import annotations

from datetime import datetime, timezone

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
    """Compose the full system prompt.

    Layout (optimized for Granite + MoE Router pattern)
    ----------------------------------------------------
    1. Kernel base — MoE Router definition, rules, constraints
    2. Available Tools — dynamic from ToolPool
    3. Available Skills — discovered from skill registry
    4. Active Expert Protocol — current MoE expert (or instruction to ORCHESTRATE)
    5. Runtime context — datetime, history summary, config
    """
    sections: list[str] = []

    # 1. Kernel base — MoE Router, rules, constraints, output format
    sections.append(load("system"))

    # 2. Available Tools — generated from the live tool registry
    tool_section = tool_pool.as_prompt_section()
    if tool_section:
        sections.append(tool_section)

    # 3. Available Skills — loaded from skill files
    try:
        skill_reg = build_skill_registry()
        if skill_reg.skills:
            skill_parts = ["<SKILLS>"]
            for s in skill_reg.skills:
                tools_csv = ", ".join(s.recommended_tools) if s.recommended_tools else "any"
                triggers_csv = ", ".join(s.triggers) if s.triggers else ""
                body_lines = s.body.strip().splitlines()
                body_preview = "\n".join(body_lines[:10]) if body_lines else ""
                skill_parts.append(
                    f'<SKILL name="{s.name}">\n'
                    f"Description: {s.description}\n"
                    f"Triggers: {triggers_csv}\n"
                    f"Tools: {tools_csv}\n"
                    f"{body_preview}\n"
                    f"</SKILL>"
                )
            skill_parts.append("</SKILLS>")
            sections.append("\n".join(skill_parts))
    except Exception:
        pass

    # 4. Active Expert Protocol (MoE Router state)
    if expert_protocol:
        sections.append(f"<ACTIVE_EXPERT_PROTOCOL>\n{expert_protocol}\n</ACTIVE_EXPERT_PROTOCOL>")
    else:
        sections.append(
            "<ACTIVE_EXPERT_PROTOCOL>\n"
            "None active. You MUST ORCHESTRATE a specialized protocol in your first response.\n"
            "Generate an <EXPERT_PROTOCOL> block as defined in <MoE_ROUTER>.\n"
            "</ACTIVE_EXPERT_PROTOCOL>"
        )

    # 5. Runtime context
    now = datetime.now(timezone.utc).astimezone()
    context_parts = [
        "<CONTEXT>",
        f"Date: {now.strftime('%Y-%m-%d %H:%M %Z')}",
        f"Config: {cfg.model_name} | retries={cfg.max_validation_retries} | bash_timeout={cfg.max_bash_timeout}s",
    ]
    if history_summary:
        context_parts.append(f"<HISTORY_SUMMARY>\n{history_summary}\n</HISTORY_SUMMARY>")
    context_parts.append("</CONTEXT>")
    sections.append("\n".join(context_parts))

    # Final directive
    sections.append("CRITICAL: Use TOOLS, not text.")

    return "\n\n".join(sections)
