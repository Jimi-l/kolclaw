
from __future__ import annotations

import re
from collections import defaultdict
from typing import Dict, List

from .schemas import (
    AgencyIntent,
    Scene,
    Stage,
    TalkTemplate,
    Tone,
    TrainingSample,
    generate_template_id,
)


SLOT_PATTERNS = [
    (re.compile(r"\d{4}-\d{1,2}-\d{1,2}"), "[DATE]"),
    (re.compile(r"\d{1,2}月\d{1,2}日"), "[DATE]"),
    (re.compile(r"\d{1,2}:\d{2}"), "[TIME]"),
    (re.compile(r"[¥￥]\s*\d+(?:\.\d+)?"), "[AMOUNT]"),
    (re.compile(r"\d+(?:\.\d+)?\s*(?:元|块|万|k|K)"), "[AMOUNT]"),
    (re.compile(r"\d{1,3}(,\d{3})*(\.\d+)?"), "[NUMBER]"),
    (re.compile(r"https?://[^\s]+"), "[URL]"),
    (re.compile(r"@[^\s，。！？,.!?]+"), "[MENTION]"),
]


def text_to_template(text: str) -> str:
    template = text
    for pattern, slot in SLOT_PATTERNS:
        template = pattern.sub(slot, template)
    return template


def compute_reusable_score(template_text: str, count: int) -> float:
    score = 0.0

    length = len(template_text)
    if 10 <= length <= 200:
        score += 0.3
    elif length > 200:
        score += 0.1

    num_slots = template_text.count("[")
    if 1 <= num_slots <= 3:
        score += 0.3
    elif num_slots > 3:
        score += 0.1

    if count >= 3:
        score += 0.2
    elif count >= 2:
        score += 0.1

    if any(kw in template_text.lower() for kw in ["你好", "您好", "谢谢", "好的", "没问题"]):
        score += 0.1

    return min(1.0, score)


def compute_business_value_score(template_text: str, stage: Stage, scene: Scene) -> float:
    score = 0.0

    high_value_stages = [
        Stage.PRICE_INQUIRY,
        Stage.PRICE_NEGOTIATION,
        Stage.BRIEF_ALIGNMENT,
        Stage.SCHEDULE_CONFIRMATION,
    ]
    if stage in high_value_stages:
        score += 0.4

    high_value_scenes = [
        Scene.EXPLAIN_PRICE,
        Scene.BARGAIN,
        Scene.SEND_BRIEF,
        Scene.CONFIRM_SCHEDULE,
        Scene.HANDLE_OBJECTION,
    ]
    if scene in high_value_scenes:
        score += 0.3

    if any(kw in template_text.lower() for kw in ["报价", "价格", "预算", "brief", "排期", "档期"]):
        score += 0.2

    length = len(template_text)
    if 20 <= length <= 300:
        score += 0.1

    return min(1.0, score)


class TemplateMiner:
    def __init__(self):
        pass

    def mine_templates(
        self,
        samples: List[TrainingSample],
    ) -> List[TalkTemplate]:
        template_groups: Dict[str, List[TrainingSample]] = defaultdict(list)

        for sample in samples:
            template_text = text_to_template(sample.agency_reply)
            template_groups[template_text].append(sample)

        templates: List[TalkTemplate] = []
        for template_text, group_samples in template_groups.items():
            count = len(group_samples)
            first_sample = group_samples[0]

            reusable_score = compute_reusable_score(template_text, count)
            business_value_score = compute_business_value_score(
                template_text, first_sample.stage, first_sample.scene
            )

            template = TalkTemplate(
                template_id=generate_template_id(template_text),
                template_text=template_text,
                example_reply=first_sample.agency_reply,
                stage=first_sample.stage,
                scene=first_sample.scene,
                agency_intent=first_sample.agency_intent,
                tone=first_sample.tone,
                count=count,
                reusable_score=reusable_score,
                business_value_score=business_value_score,
                source_sample_ids=[s.sample_id for s in group_samples],
            )
            templates.append(template)

        templates.sort(key=lambda t: (-t.reusable_score, -t.business_value_score, -t.count))

        for sample in samples:
            template_text = text_to_template(sample.agency_reply)
            sample.template_candidate = template_text

        return templates
