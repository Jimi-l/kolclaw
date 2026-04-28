from __future__ import annotations

import json
import sqlite3
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

from models import CreatorRecord, WorkflowSummary, XingtuRecord
from utils import configure_logger, dedupe_keep_order, ensure_dir, now_iso


class LocalStorage:
    def __init__(self, db_path: str | Path, log_dir: str | Path = "data/logs") -> None:
        self.db_path = Path(db_path)
        ensure_dir(self.db_path.parent)
        self.logger = configure_logger("storage", log_dir)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS creator_records (
                    record_id TEXT PRIMARY KEY,
                    creator_name TEXT NOT NULL UNIQUE,
                    platform TEXT NOT NULL,
                    follower_count INTEGER,
                    traffic_trend TEXT,
                    enrichment_status TEXT,
                    xingtu_id TEXT,
                    video_url TEXT,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS workflow_runs (
                    run_id TEXT PRIMARY KEY,
                    workflow_name TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_key TEXT PRIMARY KEY,
                    updated_at TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                """
            )

    def get_creator(self, creator_name: str) -> Optional[CreatorRecord]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM creator_records WHERE creator_name = ?",
                (creator_name,),
            ).fetchone()
        if not row:
            return None
        return CreatorRecord.from_dict(json.loads(row["payload_json"]))

    def list_creators(self, limit: int = 100) -> list[CreatorRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json
                FROM creator_records
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [CreatorRecord.from_dict(json.loads(row["payload_json"])) for row in rows]

    def get_creators_missing_xingtu(self, limit: int = 20) -> list[CreatorRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT payload_json
                FROM creator_records
                WHERE (xingtu_id IS NULL OR xingtu_id = '')
                  AND enrichment_status != 'complete'
                ORDER BY updated_at DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [CreatorRecord.from_dict(json.loads(row["payload_json"])) for row in rows]

    def upsert_creator_record(self, incoming: CreatorRecord) -> tuple[str, CreatorRecord]:
        incoming.validate()
        existing = self.get_creator(incoming.creator_name)

        if existing:
            merged = merge_creator_records(existing=existing, incoming=incoming)
            status = "updated"
            created_at = existing.created_at
        else:
            merged = incoming
            status = "created"
            created_at = incoming.created_at

        merged.created_at = created_at
        merged.updated_at = now_iso()
        merged.validate()

        xingtu_id = merged.xingtu_record.xingtu_id if merged.xingtu_record else None
        payload_json = json.dumps(merged.to_dict(), ensure_ascii=False)

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO creator_records (
                    record_id,
                    creator_name,
                    platform,
                    follower_count,
                    traffic_trend,
                    enrichment_status,
                    xingtu_id,
                    video_url,
                    payload_json,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(record_id) DO UPDATE SET
                    creator_name = excluded.creator_name,
                    platform = excluded.platform,
                    follower_count = excluded.follower_count,
                    traffic_trend = excluded.traffic_trend,
                    enrichment_status = excluded.enrichment_status,
                    xingtu_id = excluded.xingtu_id,
                    video_url = excluded.video_url,
                    payload_json = excluded.payload_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                (
                    merged.record_id,
                    merged.creator_name,
                    merged.platform,
                    merged.follower_count,
                    merged.traffic_trend,
                    merged.enrichment_status,
                    xingtu_id,
                    merged.video_candidate.video_url,
                    payload_json,
                    merged.created_at,
                    merged.updated_at,
                ),
            )

        self.logger.info("Upsert creator record (%s): %s", status, merged.creator_name)
        return status, merged

    def attach_xingtu_record(self, creator_name: str, xingtu_record: XingtuRecord) -> CreatorRecord:
        existing = self.get_creator(creator_name)
        if not existing:
            raise KeyError(f"Creator not found in local storage: {creator_name}")

        existing.xingtu_record = merge_xingtu_records(existing.xingtu_record, xingtu_record)
        existing.enrichment_status = existing.xingtu_record.match_status
        _, merged = self.upsert_creator_record(existing)
        return merged

    def save_workflow_summary(self, summary: WorkflowSummary) -> None:
        payload_json = json.dumps(summary.to_dict(), ensure_ascii=False)
        run_id = f"{summary.workflow_name}:{summary.started_at}"
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO workflow_runs (
                    run_id,
                    workflow_name,
                    status,
                    created_at,
                    payload_json
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, summary.workflow_name, summary.status, summary.started_at, payload_json),
            )
        self.logger.info("Saved workflow summary: %s", run_id)

    def save_checkpoint(self, checkpoint_key: str, payload: dict[str, Any]) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO checkpoints (
                    checkpoint_key,
                    updated_at,
                    payload_json
                ) VALUES (?, ?, ?)
                """,
                (checkpoint_key, now_iso(), json.dumps(payload, ensure_ascii=False)),
            )
        self.logger.info("Saved checkpoint: %s", checkpoint_key)

    def load_checkpoint(self, checkpoint_key: str) -> Optional[dict[str, Any]]:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT payload_json FROM checkpoints WHERE checkpoint_key = ?",
                (checkpoint_key,),
            ).fetchone()
        if not row:
            return None
        return json.loads(row["payload_json"])


def merge_creator_records(existing: CreatorRecord, incoming: CreatorRecord) -> CreatorRecord:
    merged = deepcopy(existing)
    merged.video_candidate = incoming.video_candidate or existing.video_candidate
    merged.profile_url = incoming.profile_url or existing.profile_url
    merged.follower_count = incoming.follower_count or existing.follower_count
    merged.total_likes = incoming.total_likes or existing.total_likes
    merged.recommended_video_position = incoming.recommended_video_position or existing.recommended_video_position
    merged.recommended_video_like_count = (
        incoming.recommended_video_like_count or existing.recommended_video_like_count
    )
    merged.recent_video_like_counts = incoming.recent_video_like_counts or existing.recent_video_like_counts
    merged.recent_video_average_like_count = (
        incoming.recent_video_average_like_count or existing.recent_video_average_like_count
    )
    merged.traffic_trend = incoming.traffic_trend or existing.traffic_trend
    merged.persona_tags = dedupe_keep_order(incoming.persona_tags + existing.persona_tags, limit=2)
    merged.content_tags = dedupe_keep_order(incoming.content_tags + existing.content_tags, limit=2)
    merged.scene_tags = dedupe_keep_order(incoming.scene_tags + existing.scene_tags)
    merged.ad_fit = incoming.ad_fit or existing.ad_fit
    merged.analysis_notes = dedupe_keep_order(existing.analysis_notes + incoming.analysis_notes)

    if incoming.xingtu_record:
        merged.xingtu_record = merge_xingtu_records(existing.xingtu_record, incoming.xingtu_record)
        merged.enrichment_status = merged.xingtu_record.match_status
    else:
        merged.xingtu_record = existing.xingtu_record
        merged.enrichment_status = existing.enrichment_status

    return merged


def merge_xingtu_records(
    existing: Optional[XingtuRecord],
    incoming: XingtuRecord,
) -> XingtuRecord:
    if existing is None:
        incoming.validate()
        return incoming

    merged = deepcopy(existing)
    merged.xingtu_id = incoming.xingtu_id or existing.xingtu_id
    merged.creator_types = dedupe_keep_order(incoming.creator_types + existing.creator_types)
    merged.profile_url = incoming.profile_url or existing.profile_url
    merged.price_20s = incoming.price_20s or existing.price_20s
    merged.price_20_to_60s = incoming.price_20_to_60s or existing.price_20_to_60s
    merged.price_60s_plus = incoming.price_60s_plus or existing.price_60s_plus
    merged.estimated_play_volume = incoming.estimated_play_volume or existing.estimated_play_volume
    merged.sponsored_play_median = incoming.sponsored_play_median or existing.sponsored_play_median
    merged.organic_cpm = incoming.organic_cpm or existing.organic_cpm
    merged.cpe = incoming.cpe or existing.cpe
    merged.completion_rate = incoming.completion_rate or existing.completion_rate
    merged.play_curve_screenshot = incoming.play_curve_screenshot or existing.play_curve_screenshot
    merged.monthly_follower_growth_rate = (
        incoming.monthly_follower_growth_rate or existing.monthly_follower_growth_rate
    )
    merged.connected_user_fan_ratio = incoming.connected_user_fan_ratio or existing.connected_user_fan_ratio
    merged.deep_user_fan_ratio = incoming.deep_user_fan_ratio or existing.deep_user_fan_ratio
    merged.cooperative_clients = dedupe_keep_order(incoming.cooperative_clients + existing.cooperative_clients)
    merged.match_status = incoming.match_status or existing.match_status
    merged.notes = dedupe_keep_order(existing.notes + incoming.notes)
    merged.validate()
    return merged
