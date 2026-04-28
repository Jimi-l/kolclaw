from __future__ import annotations

import logging
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from search_agent.artifacts import ArtifactManager
from search_agent.browser.session import BrowserSession
from search_agent.config import BrowserConfig, Mp4LinkRunConfig, RuntimePaths
from search_agent.enums import WorkflowStage
from search_agent.models.common import RunSummary
from search_agent.models.discovery import CreatorDiscoveryRecord
from search_agent.models.mp4_links import Mp4LinkRecord
from search_agent.storage.jsonl_store import JsonlStore

from .mp4_resolver import BrowserContextOnlyMp4Error, DouyinMp4Resolver, Mp4ResolveResult


ResolverFactory = Callable[[Any, Any, logging.Logger, int], Any]


class DouyinMp4LinkWorkflow:
    def __init__(
        self,
        paths: RuntimePaths,
        artifacts: ArtifactManager,
        browser_config: BrowserConfig,
        run_config: Mp4LinkRunConfig,
        resolver_factory: ResolverFactory | None = None,
    ) -> None:
        self.paths = paths
        self.artifacts = artifacts
        self.browser_config = browser_config
        self.run_config = run_config
        self.logger = logging.getLogger("search_agent.mp4_links")
        self.discovery_store = JsonlStore(self.paths.discovery_output, CreatorDiscoveryRecord)
        self.mp4_store = JsonlStore(self.paths.mp4_links_output, Mp4LinkRecord)
        self.resolver_factory = resolver_factory or DouyinMp4Resolver

    def run(self) -> RunSummary:
        self.paths.ensure_directories()
        processed = completed = skipped = blocked = 0
        batches_run = 0
        start_time = time.monotonic()
        last_flush_at = start_time

        while True:
            pending = self._pending_records()
            batch_size = max(self.run_config.batch_size, 1)
            should_process = bool(pending) and (
                not self.run_config.watch
                or len(pending) >= batch_size
                or (time.monotonic() - last_flush_at) >= self.run_config.flush_seconds
            )
            if should_process:
                batch = pending[:batch_size]
                batch_processed, batch_completed, batch_skipped = self._process_batch(batch)
                processed += batch_processed
                completed += batch_completed
                skipped += batch_skipped
                batches_run += 1
                last_flush_at = time.monotonic()

            if not self.run_config.watch:
                break
            if self.run_config.max_batches is not None and batches_run >= self.run_config.max_batches:
                break
            time.sleep(max(self.run_config.poll_seconds, 0.1))

        duration_minutes = round((time.monotonic() - start_time) / 60, 2)
        return RunSummary(
            stage=WorkflowStage.DOUYIN_MP4_LINKS,
            run_id=self.artifacts.run_id,
            duration_minutes=duration_minutes,
            processed_candidates=processed,
            successful_records=completed,
            skipped_items=skipped,
            blocked_items=blocked,
            next_stage_ready=completed,
            output_path=str(self.paths.mp4_links_output),
            queue_path=None,
        )

    def _pending_records(self) -> list[CreatorDiscoveryRecord]:
        latest_by_url: dict[str, CreatorDiscoveryRecord] = {}
        for record in self.discovery_store.load_all():
            if self.run_config.workflow_run_id and record.workflow_run_id != self.run_config.workflow_run_id:
                continue
            video_url = (record.video_url or "").strip()
            if not video_url:
                continue
            latest_by_url[video_url] = record

        existing_by_url = {
            record.video_url: record
            for record in self.mp4_store.load_all()
            if not self.run_config.workflow_run_id or record.workflow_run_id == self.run_config.workflow_run_id
        }
        pending: list[CreatorDiscoveryRecord] = []
        for video_url, record in latest_by_url.items():
            existing = existing_by_url.get(video_url)
            if self._should_skip_existing(existing):
                continue
            pending.append(record)
        return pending

    def _should_skip_existing(self, existing: Mp4LinkRecord | None) -> bool:
        if existing is None or self.run_config.force:
            return False
        if existing.status == "success":
            return True
        if existing.status == "failed" and not self.run_config.retry_failed:
            return True
        if existing.status == "processing" and not self.run_config.retry_failed:
            return True
        return False

    def _process_batch(self, records: list[CreatorDiscoveryRecord]) -> tuple[int, int, int]:
        if not records:
            return 0, 0, 0

        processed = completed = skipped = 0
        for record in records:
            self._mark_processing(record)

        session_path = self.paths.browser_state_dir / self.browser_config.site_name
        with BrowserSession(self.browser_config, session_path) as browser:
            resolver = self.resolver_factory(
                browser.page,
                browser.context,
                self.logger,
                self.run_config.page_wait_ms,
            )
            for record in records:
                processed += 1
                try:
                    result = resolver.resolve(record)
                    self._mark_success(record, result)
                    completed += 1
                except BrowserContextOnlyMp4Error as exc:
                    self._mark_failed(record, str(exc), result=exc.result)
                    skipped += 1
                    self.logger.warning(
                        "douyin mp4 link is browser-context-only",
                        extra={
                            "record_id": record.record_id,
                            "video_url": record.video_url,
                            "direct_mp4_url": exc.result.direct_mp4_url,
                            "error_text": str(exc),
                        },
                    )
                except Exception as exc:
                    self._mark_failed(record, str(exc))
                    skipped += 1
                    self.logger.warning(
                        "douyin mp4 link resolution failed",
                        extra={
                            "record_id": record.record_id,
                            "video_url": record.video_url,
                            "error_text": str(exc),
                        },
                    )
        return processed, completed, skipped

    def _mark_processing(self, record: CreatorDiscoveryRecord) -> None:
        existing = self._existing_for(record)
        self.mp4_store.upsert(
            Mp4LinkRecord(
                record_id=record.record_id,
                workflow_run_id=record.workflow_run_id,
                video_url=record.video_url or "",
                creator_name=record.creator_name,
                status="processing",
                direct_mp4_url=existing.direct_mp4_url if existing else None,
                source=existing.source if existing else None,
                access_mode=existing.access_mode if existing else None,
                final_url=existing.final_url if existing else None,
                content_type=existing.content_type if existing else None,
                content_length=existing.content_length if existing else None,
                probe_status_code=existing.probe_status_code if existing else None,
                probe_content_range=existing.probe_content_range if existing else None,
                attempt_count=(existing.attempt_count if existing else 0) + 1,
                last_error=None,
                updated_at=_utc_now_iso(),
            ),
            key_field="video_url",
        )

    def _mark_success(self, record: CreatorDiscoveryRecord, result: Mp4ResolveResult) -> None:
        existing = self._existing_for(record)
        self.mp4_store.upsert(
            Mp4LinkRecord(
                record_id=record.record_id,
                workflow_run_id=record.workflow_run_id,
                video_url=record.video_url or "",
                creator_name=record.creator_name,
                status="success",
                direct_mp4_url=result.direct_mp4_url,
                source=result.source,
                access_mode=result.access_mode,
                final_url=result.final_url,
                content_type=result.content_type,
                content_length=result.content_length,
                probe_status_code=result.probe_status_code,
                probe_content_range=result.probe_content_range,
                attempt_count=existing.attempt_count if existing else 1,
                last_error=None,
                updated_at=_utc_now_iso(),
            ),
            key_field="video_url",
        )

    def _mark_failed(self, record: CreatorDiscoveryRecord, error_text: str, result: Mp4ResolveResult | None = None) -> None:
        existing = self._existing_for(record)
        self.mp4_store.upsert(
            Mp4LinkRecord(
                record_id=record.record_id,
                workflow_run_id=record.workflow_run_id,
                video_url=record.video_url or "",
                creator_name=record.creator_name,
                status="failed",
                direct_mp4_url=result.direct_mp4_url if result else None,
                source=result.source if result else None,
                access_mode=result.access_mode if result else "failed",
                final_url=result.final_url if result else None,
                content_type=result.content_type if result else None,
                content_length=result.content_length if result else None,
                probe_status_code=result.probe_status_code if result else None,
                probe_content_range=result.probe_content_range if result else None,
                attempt_count=existing.attempt_count if existing else 1,
                last_error=error_text,
                updated_at=_utc_now_iso(),
            ),
            key_field="video_url",
        )

    def _existing_for(self, record: CreatorDiscoveryRecord) -> Mp4LinkRecord | None:
        video_url = record.video_url or ""
        for existing in self.mp4_store.load_all():
            if existing.video_url == video_url and (
                not self.run_config.workflow_run_id or existing.workflow_run_id == self.run_config.workflow_run_id
            ):
                return existing
        return None


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()
