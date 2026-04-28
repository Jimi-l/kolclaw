from __future__ import annotations

import re
from typing import Protocol

from search_agent.models.common import TaggingContext, TaggingResult
from search_agent.tagging.taxonomy import (
    CONTENT_RULES,
    INTEREST_KEYWORDS,
    LIFE_KEYWORDS,
    MONETIZATION_KEYWORDS,
    PROFESSION_KEYWORDS,
    RELATION_KEYWORDS,
)


class TaggingBackend(Protocol):
    def tag(self, context: TaggingContext) -> TaggingResult:
        ...


def _contains_keyword(text: str, keyword: str) -> bool:
    return keyword.lower() in text


def _join_text(parts: list[str | None]) -> str:
    return " ".join(part.strip() for part in parts if part and part.strip())


def _score_rule(text: str, keywords: tuple[str, ...], negative_keywords: tuple[str, ...]) -> int:
    if not text:
        return 0
    lowered = text.lower()
    if any(_contains_keyword(lowered, token) for token in negative_keywords):
        return 0
    return sum(1 for token in keywords if _contains_keyword(lowered, token))


def _pick_content_rule(text: str):
    best_rule = None
    best_score = 0
    for rule in CONTENT_RULES:
        score = _score_rule(text, rule.keywords, rule.negative_keywords)
        if score <= 0:
            continue
        if score > best_score:
            best_rule = rule
            best_score = score
            continue
        if score == best_score and best_rule is not None and len(rule.path) > len(best_rule.path):
            best_rule = rule
    return best_rule, best_score


def _match_explicit_tags(text: str, mapping: dict[str, tuple[str, ...]], limit: int | None = None) -> list[str]:
    matches: list[str] = []
    lowered = text.lower()
    for tag, aliases in mapping.items():
        if any(_contains_keyword(lowered, alias) for alias in aliases):
            matches.append(tag)
            if limit is not None and len(matches) >= limit:
                break
    return matches


def _derive_cooperate_type(context: TaggingContext) -> str | None:
    duration_seconds = context.video_duration_seconds
    if duration_seconds is None:
        duration_seconds = _extract_total_duration_seconds(
            context.recommendation_video_summary,
            context.video_description_raw,
            context.video_title_text,
            context.video_text_bundle,
        )
    if duration_seconds is None or duration_seconds <= 0:
        return None
    if duration_seconds <= 20:
        return "图文 / 视频20s"
    if duration_seconds <= 60:
        return "21-60s"
    return "60s+"


def _extract_total_duration_seconds(*values: str | None) -> int | None:
    for value in values:
        if not value:
            continue
        match = re.search(r"\b\d{1,2}:\d{2}\s*/\s*(\d{1,2}:\d{2})\b", value)
        if not match:
            continue
        total = match.group(1)
        minutes, seconds = total.split(":")
        return int(minutes) * 60 + int(seconds)
    return None


class HeuristicTagger:
    def __init__(self, fallback_backend: TaggingBackend | None = None):
        self.fallback_backend = fallback_backend

    def tag(self, context: TaggingContext) -> TaggingResult:
        content_evidence_text = _join_text(
            [
                context.video_title_text,
                context.expanded_description_text,
                context.video_description_raw,
                context.recommendation_video_summary,
                context.video_text_bundle,
                *context.chapter_texts,
                *context.related_search_terms,
                *context.recent_videos_summary,
                *context.visible_subtitle_segments,
            ]
        ).lower()
        identity_evidence_text = _join_text(
            [
                context.creator_name,
                context.profile_bio,
                *context.author_statement_texts,
            ]
        ).lower()
        relation_evidence_text = _join_text(
            [
                content_evidence_text,
                identity_evidence_text,
                *[comment.text for comment in context.top_comments],
            ]
        ).lower()
        commercial_evidence_text = _join_text(
            [
                context.video_title_text,
                context.expanded_description_text,
                context.video_description_raw,
                context.video_text_bundle,
                *context.author_statement_texts,
                *[comment.text for comment in context.top_comments],
            ]
        ).lower()

        best_rule, best_score = _pick_content_rule(content_evidence_text)
        content_taxonomy_path = list(best_rule.path) if best_rule else []
        content_leaf_tags = [best_rule.path[-1]] if best_rule else []
        profession_tags = _match_explicit_tags(identity_evidence_text, PROFESSION_KEYWORDS, limit=3)
        interest_tags = _match_explicit_tags(relation_evidence_text, INTEREST_KEYWORDS, limit=3)
        life_tags = _match_explicit_tags(relation_evidence_text, LIFE_KEYWORDS, limit=3)
        appearance_relation_tags = _match_explicit_tags(relation_evidence_text, RELATION_KEYWORDS, limit=3)
        monetization = _match_explicit_tags(commercial_evidence_text, MONETIZATION_KEYWORDS)
        cooperate_type = _derive_cooperate_type(context)

        reasoning_parts: list[str] = []
        if best_rule:
            reasoning_parts.append(
                f"内容标签依据命中 KolClaw taxonomy：{' -> '.join(best_rule.path)}（匹配到 {best_score} 个内容关键词）"
            )
        else:
            reasoning_parts.append("内容标签未命中明确 taxonomy 证据，建议后续结合更多评论/字幕补充判断")
        if profession_tags:
            reasoning_parts.append(f"职业标签依据主要来自昵称/简介中的显式身份词：{', '.join(profession_tags)}")
        if interest_tags:
            reasoning_parts.append(f"兴趣标签依据主要来自标题/简介/评论中的显式兴趣词：{', '.join(interest_tags)}")
        if life_tags:
            reasoning_parts.append(f"生活标签依据主要来自显式生活状态词：{', '.join(life_tags)}")
        if appearance_relation_tags:
            reasoning_parts.append(f"出镜关系标签依据主要来自显式关系词：{', '.join(appearance_relation_tags)}")
        if monetization:
            reasoning_parts.append(f"商业合作标签依据主要来自明确变现信号：{', '.join(monetization)}")
        else:
            reasoning_parts.append("未检测到明确商业合作信号，monetization 保持为空")
        if cooperate_type:
            reasoning_parts.append(f"合作方式依据视频总时长推断为：{cooperate_type}")

        result = TaggingResult(
            content_taxonomy_path=content_taxonomy_path,
            content_leaf_tags=content_leaf_tags,
            profession_tags=profession_tags,
            interest_tags=interest_tags,
            life_tags=life_tags,
            appearance_relation_tags=appearance_relation_tags,
            monetization=monetization,
            cooperate_type=cooperate_type,
            label_reasoning="；".join(reasoning_parts),
        )

        if self.fallback_backend and not result.content_taxonomy_path:
            return self.fallback_backend.tag(context)
        return result
