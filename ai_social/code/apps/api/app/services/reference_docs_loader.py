from __future__ import annotations

import re
from pathlib import Path

from app.core.config import get_settings
from app.schemas.reference_docs import ExternalDocReference

KNOWN_USAGE_RULES: dict[str, dict[str, object]] = {
    "AI智能巡号_抖音版_执行提示词_V3": {
        "used_in_v1": True,
        "usage_notes": [
            "Used only for content-tagging and candidate-observation heuristics.",
            "Not used to implement autonomous Douyin feed scouting in V1.",
        ],
    },
    "AI智能巡号_星图数据补充_执行提示词": {
        "used_in_v1": True,
        "usage_notes": [
            "Used for Xingtu field coverage and detail-metric extraction priorities.",
        ],
    },
    "KOLClaw-Prompt优化工程：": {
        "used_in_v1": True,
        "usage_notes": [
            "Used for prompt/module boundary awareness, not for adding RAG or multi-agent scope.",
        ],
    },
    "KOLclaw 媒介执行workflow": {
        "used_in_v1": True,
        "usage_notes": [
            "Used for shaping the shortlist workflow stages and operator-facing output.",
        ],
    },
    "KolClaw达人标签": {
        "used_in_v1": True,
        "usage_notes": [
            "Used for creator category and tag naming references.",
        ],
    },
    "「KOLClaw」AI媒介代理执行计划": {
        "used_in_v1": True,
        "usage_notes": [
            "Used for demo framing and shortlist-assistant output expectations.",
        ],
    },
    "选号prompt": {
        "used_in_v1": True,
        "usage_notes": [
            "Used for heuristic quality scoring and shortlist prioritization signals.",
        ],
    },
    "KOLClaw_AI_Super_Employee(1)": {
        "used_in_v1": False,
        "usage_notes": [
            "Indexed as archive context only.",
        ],
    },
}


class ReferenceDocsLoader:
    """Indexes local external reference docs without introducing a retrieval system."""

    def __init__(self, docs_root: Path | None = None) -> None:
        settings = get_settings()
        self.settings = settings
        self.docs_root = docs_root or settings.external_docs_root

    def list_references(
        self,
        category: str | None = None,
        used_in_v1_only: bool = False,
    ) -> list[ExternalDocReference]:
        references: list[ExternalDocReference] = []
        for path in sorted(self.docs_root.rglob("*")):
            if not path.is_file():
                continue
            doc_category = path.parent.name
            if category and doc_category != category:
                continue

            stem = path.stem
            usage_rule = KNOWN_USAGE_RULES.get(stem, {})
            used_in_v1 = bool(usage_rule.get("used_in_v1", False))
            if used_in_v1_only and not used_in_v1:
                continue

            references.append(
                ExternalDocReference(
                    doc_id=_slugify(stem),
                    title=stem,
                    category=doc_category,
                    relative_path=str(path.relative_to(self.settings.workspace_root)),
                    absolute_path=str(path.resolve()),
                    source_type=path.suffix.lstrip(".").lower(),
                    used_in_v1=used_in_v1,
                    usage_notes=list(usage_rule.get("usage_notes", [])),
                )
            )
        return references

    def list_v1_operational_references(self) -> list[ExternalDocReference]:
        return self.list_references(category="operational", used_in_v1_only=True)


def _slugify(value: str) -> str:
    lowered = value.strip().lower()
    lowered = re.sub(r"[^\w\u4e00-\u9fff]+", "-", lowered)
    return lowered.strip("-") or "reference-doc"
