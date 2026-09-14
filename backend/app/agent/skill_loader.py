"""Controlled Skill registry - the ONLY way skill content can be loaded.

Skills are procedural instructions (SKILL.md files) teaching the agent HOW
to perform a specific FlockGuard job. `load_skill` accepts nothing but a
name already present in SKILL_REGISTRY below - there is no code path that
accepts a filesystem path from a caller, model output, or request body, so
`load_skill("../../secret")` is structurally impossible, not merely
rejected by a check.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"

# The only valid skill names. Adding a skill means adding an entry here
# AND the corresponding directory - never inferred from user/model input.
SKILL_REGISTRY: dict[str, Path] = {
    "flock_monitoring": _SKILLS_DIR / "flock_monitoring" / "SKILL.md",
    "investigate_flock_risk": _SKILLS_DIR / "investigate_flock_risk" / "SKILL.md",
    "inspection_planning": _SKILLS_DIR / "inspection_planning" / "SKILL.md",
    "daily_farm_brief": _SKILLS_DIR / "daily_farm_brief" / "SKILL.md",
    "farm_priority": _SKILLS_DIR / "farm_priority" / "SKILL.md",
    "poultry_safety": _SKILLS_DIR / "poultry_safety" / "SKILL.md",
    "general_poultry_knowledge": _SKILLS_DIR / "general_poultry_knowledge" / "SKILL.md",
}


class UnknownSkillError(ValueError):
    pass


@lru_cache(maxsize=None)
def load_skill(name: str) -> str:
    if name not in SKILL_REGISTRY:
        raise UnknownSkillError(f"Unknown skill: {name!r}. Valid skills: {sorted(SKILL_REGISTRY)}")
    return SKILL_REGISTRY[name].read_text(encoding="utf-8")


def available_skills() -> list[str]:
    return sorted(SKILL_REGISTRY)
