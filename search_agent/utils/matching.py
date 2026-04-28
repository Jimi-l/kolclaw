from __future__ import annotations

import re

from search_agent.enums import MatchConfidence, NextAction
from search_agent.models.common import MatchDecision
from search_agent.models.discovery import CreatorDiscoveryRecord
from search_agent.utils.dedup import normalize_name
from search_agent.utils.normalize import normalize_chinese_count


def _bucket(value: int | None) -> int | None:
    if value is None:
        return None
    if value < 10_000:
        return 1
    if value < 100_000:
        return 2
    if value < 1_000_000:
        return 3
    return 4


def _content_tokens(*values: str | None) -> set[str]:
    tokens: set[str] = set()
    for value in values:
        if not value:
            continue
        text = re.sub(r"[^\w\u4e00-\u9fff]+", " ", value.lower())
        tokens.update(token for token in text.split() if len(token) > 1)
    return tokens


def evaluate_xingtu_match(
    discovery_record: CreatorDiscoveryRecord,
    candidate_name: str | None,
    candidate_follower_hint: str | None,
    candidate_creator_type: str | None,
    candidate_content_hint: str | None,
    avatar_style_match: bool | None = None,
) -> MatchDecision:
    score = 0
    conflicts: list[str] = []
    reasons: list[str] = []

    discovery_name = normalize_name(discovery_record.creator_name)
    xingtu_name = normalize_name(candidate_name)
    if discovery_name == xingtu_name and discovery_name != "unknown":
        score += 3
        reasons.append("达人名称高度一致")
    elif discovery_name != "unknown" and xingtu_name != "unknown" and (
        discovery_name in xingtu_name or xingtu_name in discovery_name
    ):
        score += 2
        reasons.append("达人名称存在稳定简称/变体")
    else:
        conflicts.append("名称不一致或仅模糊近似")

    discovery_bucket = _bucket(discovery_record.follower_count_normalized)
    candidate_bucket = _bucket(normalize_chinese_count(candidate_follower_hint))
    if discovery_bucket is not None and candidate_bucket is not None:
        if discovery_bucket == candidate_bucket:
            score += 2
            reasons.append("粉丝量量级一致")
        elif abs(discovery_bucket - candidate_bucket) == 1:
            score += 1
            reasons.append("粉丝量量级接近")
        else:
            conflicts.append("粉丝量量级明显不符")
            score -= 3
    else:
        conflicts.append("缺少粉丝量量级线索")

    discovery_tokens = _content_tokens(
        *discovery_record.content_taxonomy_path,
        *discovery_record.content_leaf_tags,
        *discovery_record.profession_tags,
        *discovery_record.interest_tags,
    )
    candidate_tokens = _content_tokens(candidate_creator_type, candidate_content_hint)
    if discovery_tokens and candidate_tokens:
        overlap = discovery_tokens & candidate_tokens
        if overlap:
            score += 2
            reasons.append(f"内容方向一致：{', '.join(sorted(overlap))}")
        else:
            conflicts.append("内容方向不一致")
            score -= 2
    else:
        conflicts.append("内容方向线索不足")

    if avatar_style_match is True:
        score += 1
        reasons.append("头像/主页风格一致")
    elif avatar_style_match is False:
        conflicts.append("头像/主页风格冲突")
        score -= 2

    if score >= 6 and not any("明显" in item or "冲突" in item for item in conflicts):
        return MatchDecision(
            is_same_creator=True,
            match_confidence=MatchConfidence.HIGH,
            match_reason="；".join(reasons) or "名称、粉丝量和内容方向均较一致",
            conflict_points=conflicts,
            next_action=NextAction.CONTINUE,
            score=score,
        )
    if score >= 4 and "粉丝量量级明显不符" not in conflicts and "头像/主页风格冲突" not in conflicts:
        return MatchDecision(
            is_same_creator=False,
            match_confidence=MatchConfidence.MEDIUM,
            match_reason="；".join(reasons) or "存在部分一致信号，但仍需谨慎复核",
            conflict_points=conflicts,
            next_action=NextAction.CONTINUE_WITH_CAUTION,
            score=score,
        )
    return MatchDecision(
        is_same_creator=False,
        match_confidence=MatchConfidence.LOW,
        match_reason="；".join(reasons) if reasons else "同名歧义或关键身份线索不足，无法确认同一达人",
        conflict_points=conflicts,
        next_action=NextAction.MANUAL_REVIEW,
        score=score,
    )
