from __future__ import annotations

import json
from pathlib import Path

from fastapi import HTTPException

from app.core.config import get_settings
from app.schemas.strategy_template import StrategyTemplate


class StrategyLoader:
    """Loads reusable strategy templates from local JSON files."""

    def __init__(self, templates_dir: Path | None = None) -> None:
        settings = get_settings()
        self.templates_dir = templates_dir or settings.strategy_templates_dir

    def list_templates(self) -> list[StrategyTemplate]:
        templates: list[StrategyTemplate] = []
        for path in sorted(self.templates_dir.glob("*.json")):
            with path.open("r", encoding="utf-8") as file:
                templates.append(StrategyTemplate.model_validate(json.load(file)))
        return templates

    def get_template(self, template_id: str) -> StrategyTemplate:
        for template in self.list_templates():
            if template.template_id == template_id:
                return template
        raise HTTPException(status_code=404, detail=f"Strategy template `{template_id}` not found.")
