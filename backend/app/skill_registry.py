from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.models import SkillDefinition


@dataclass(frozen=True)
class SkillSpec:
    definition: SkillDefinition
    prompt: str
    guide: str
    schema: dict[str, Any]


def skills_root() -> Path:
    return Path(__file__).parent / "skills"


@lru_cache(maxsize=1)
def load_skill_specs() -> dict[str, SkillSpec]:
    specs: dict[str, SkillSpec] = {}
    for directory in sorted(path for path in skills_root().iterdir() if path.is_dir()):
        schema = json.loads((directory / "schema.json").read_text(encoding="utf-8"))
        prompt = (directory / "prompt.md").read_text(encoding="utf-8")
        guide = (directory / "SKILL.md").read_text(encoding="utf-8")
        definition = SkillDefinition.model_validate(
            {
                "id": schema["id"],
                "name": schema["name"],
                "description": schema["description"],
                "required_inputs": schema.get("required_inputs", []),
                "output_types": schema.get("output_types", []),
                "can_update_assets": schema.get("can_update_assets", False),
            }
        )
        specs[definition.id] = SkillSpec(definition=definition, prompt=prompt, guide=guide, schema=schema)
    return specs


def get_skill_spec(skill_id: str) -> SkillSpec | None:
    return load_skill_specs().get(skill_id)


def list_skill_definitions() -> list[SkillDefinition]:
    return [spec.definition for spec in load_skill_specs().values()]

