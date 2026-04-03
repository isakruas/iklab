from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

import yaml

from .config import get_config


@dataclass(frozen=True)
class SkillMeta:
    name: str
    description: str
    triggers: Tuple[str, ...]
    recommended_tools: Tuple[str, ...]
    body: str
    source_path: str


class SkillRegistry:
    def __init__(self, skills: Tuple[SkillMeta, ...]):
        self.skills = skills

    def get(self, name: str) -> SkillMeta | None:
        for s in self.skills:
            if s.name == name:
                return s
        return None

    def names(self) -> List[str]:
        return sorted(s.name for s in self.skills)

    def find_by_trigger(self, query: str) -> List[SkillMeta]:
        q = query.lower()
        return [s for s in self.skills if any(q in t.lower() for t in s.triggers)]


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""


def _parse_front_matter(text: str):
    # Very small front-matter parser: expect YAML between '---' lines at top
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except Exception:
        meta = {}
    body = parts[2].strip()
    return meta, body


def build_skill_registry() -> SkillRegistry:
    cfg = get_config()
    candidates: List[Path] = []

    # collect skill search paths from config
    for p in getattr(cfg, "skills_paths", (".iklab/skills",)):
        if not p:
            continue
        candidate = Path(p)
        if not candidate.exists():
            candidate = Path(os.getcwd()) / p
        if candidate.exists():
            if candidate.is_dir():
                candidates.append(candidate)
            elif candidate.is_file():
                candidates.append(candidate.parent)

    # also check local .iklab/skills if not already included
    local = Path(os.getcwd()) / ".iklab" / "skills"
    if local.exists() and local not in candidates:
        candidates.append(local)

    # also check package-internal skills directory (iklab/skills/)
    pkg_skills = Path(__file__).parent / "skills"
    if pkg_skills.exists() and pkg_skills.is_dir() and pkg_skills not in candidates:
        candidates.append(pkg_skills)

    found: List[SkillMeta] = []
    for dirpath in candidates:
        for f in sorted(dirpath.glob("*.md")) + sorted(dirpath.glob("*.markdown")) + sorted(dirpath.glob("*.txt")):
            text = _read_text(f)
            meta, body = _parse_front_matter(text)
            name = meta.get("name") or f.stem
            description = meta.get("description") or (body.splitlines()[0] if body else "")
            triggers = tuple(meta.get("triggers") or [])
            recommended_tools = tuple(meta.get("recommended_tools") or meta.get("tools") or [])
            found.append(
                SkillMeta(
                    name=name,
                    description=description,
                    triggers=triggers,
                    recommended_tools=recommended_tools,
                    body=body,
                    source_path=str(f),
                )
            )

    return SkillRegistry(skills=tuple(found))
