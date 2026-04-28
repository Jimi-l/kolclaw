from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import date

from search_agent.models.discovery import CreatorDiscoveryRecord


def normalize_name(name: str | None) -> str:
    if not name:
        return "unknown"
    lowered = name.strip().lower()
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]+", "", lowered) or "unknown"


def build_duplicate_key(platform: str, creator_name: str | None) -> str:
    return f"{platform}::{normalize_name(creator_name)}"


def build_record_id(
    creator_name: str | None,
    collection_date: date | None = None,
    prefix: str = "dy",
) -> str:
    current_date = collection_date or date.today()
    slug = normalize_name(creator_name)
    token = hashlib.sha1(f"{slug}|{current_date.isoformat()}".encode("utf-8")).hexdigest()[:4]
    return f"{prefix}_{slug}_{current_date.strftime('%Y%m%d')}_{token}"


@dataclass(slots=True)
class DuplicateDecision:
    is_duplicate: bool
    requires_manual_review: bool
    matched_record_id: str | None
    reason: str


def _magnitude_bucket(value: int | None) -> int | None:
    if value is None or value <= 0:
        return None
    if value < 10_000:
        return 1
    if value < 100_000:
        return 2
    if value < 1_000_000:
        return 3
    return 4


def decide_duplicate(
    candidate: CreatorDiscoveryRecord,
    existing_records: list[CreatorDiscoveryRecord],
) -> DuplicateDecision:
    for existing in existing_records:
        if existing.duplicate_key != candidate.duplicate_key:
            continue
        existing_bucket = _magnitude_bucket(existing.follower_count_normalized)
        candidate_bucket = _magnitude_bucket(candidate.follower_count_normalized)
        if existing_bucket is not None and candidate_bucket is not None and abs(existing_bucket - candidate_bucket) > 1:
            return DuplicateDecision(
                is_duplicate=False,
                requires_manual_review=True,
                matched_record_id=existing.record_id,
                reason="同名达人粉丝量量级差异较大，建议人工复核",
            )
        existing_tags = set(existing.content_leaf_tags or existing.content_taxonomy_path or [])
        candidate_tags = set(candidate.content_leaf_tags or candidate.content_taxonomy_path or [])
        if existing_tags and candidate_tags and existing_tags.isdisjoint(candidate_tags):
            return DuplicateDecision(
                is_duplicate=False,
                requires_manual_review=True,
                matched_record_id=existing.record_id,
                reason="同名达人内容方向冲突，建议人工复核",
            )
        return DuplicateDecision(
            is_duplicate=True,
            requires_manual_review=False,
            matched_record_id=existing.record_id,
            reason="重复达人，且不是新的独立账号画像",
        )
    return DuplicateDecision(
        is_duplicate=False,
        requires_manual_review=False,
        matched_record_id=None,
        reason="未发现重复记录",
    )
