from __future__ import annotations

import hashlib
import logging
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib import error, request

from search_agent.artifacts import ArtifactManager
from search_agent.config import Mp4FileUploadRunConfig, PACKAGE_ROOT, RuntimePaths
from search_agent.enums import WorkflowStage
from search_agent.exceptions import MissingDependencyError
from search_agent.models.common import RunSummary
from search_agent.models.mp4_file_uploads import Mp4FileUploadRecord
from search_agent.models.mp4_links import Mp4LinkRecord
from search_agent.storage.jsonl_store import JsonlStore


DOWNLOAD_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/123.0.0.0 Safari/537.36"
)

FileClientFactory = Callable[[str, str], Any]


class DownloadedMp4:
    def __init__(self, path: Path, content_type: str | None, content_length: str | None, downloaded_bytes: int, sha256: str):
        self.path = path
        self.content_type = content_type
        self.content_length = content_length
        self.downloaded_bytes = downloaded_bytes
        self.sha256 = sha256


class DouyinMp4FileUploadWorkflow:
    def __init__(
        self,
        paths: RuntimePaths,
        artifacts: ArtifactManager,
        run_config: Mp4FileUploadRunConfig,
        file_client_factory: FileClientFactory | None = None,
    ) -> None:
        self.paths = paths
        self.artifacts = artifacts
        self.run_config = run_config
        self.logger = logging.getLogger("search_agent.mp4_file_uploads")
        self.mp4_store = JsonlStore(self.paths.mp4_links_output, Mp4LinkRecord)
        self.upload_store = JsonlStore(self.paths.mp4_file_uploads_output, Mp4FileUploadRecord)
        self.file_client_factory = file_client_factory or _build_ark_client

    def run(self) -> RunSummary:
        self.paths.ensure_directories()
        _load_dotenv_if_available()

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
            stage=WorkflowStage.DOUYIN_MP4_FILES,
            run_id=self.artifacts.run_id,
            duration_minutes=duration_minutes,
            processed_candidates=processed,
            successful_records=completed,
            skipped_items=skipped,
            blocked_items=blocked,
            next_stage_ready=completed,
            output_path=str(self.paths.mp4_file_uploads_output),
            queue_path=None,
        )

    def _pending_records(self) -> list[Mp4LinkRecord]:
        latest_by_url: dict[str, Mp4LinkRecord] = {}
        for record in self.mp4_store.load_all():
            if self.run_config.workflow_run_id and record.workflow_run_id != self.run_config.workflow_run_id:
                continue
            if not _is_uploadable_mp4(record):
                continue
            latest_by_url[record.video_url] = record

        existing_by_url = {
            record.video_url: record
            for record in self.upload_store.load_all()
            if not self.run_config.workflow_run_id or record.workflow_run_id == self.run_config.workflow_run_id
        }
        pending: list[Mp4LinkRecord] = []
        for video_url, record in latest_by_url.items():
            existing = existing_by_url.get(video_url)
            if self._should_skip_existing(existing):
                continue
            pending.append(record)
        return pending

    def _should_skip_existing(self, existing: Mp4FileUploadRecord | None) -> bool:
        if existing is None or self.run_config.force:
            return False
        if existing.status == "success":
            return True
        if existing.status == "failed" and not self.run_config.retry_failed:
            return True
        if existing.status in {"downloading", "uploading"} and not self.run_config.retry_failed:
            return True
        return False

    def _process_batch(self, records: list[Mp4LinkRecord]) -> tuple[int, int, int]:
        processed = completed = skipped = 0
        if not records:
            return processed, completed, skipped

        api_key = os.getenv("ARK_API_KEY")
        if not api_key:
            for record in records:
                self._mark_failed(record, "ARK_API_KEY is not set; put it in search_agent/local_only/env/search_agent.env or export it.")
            return len(records), 0, len(records)

        try:
            client = self.file_client_factory(self.run_config.ark_base_url, api_key)
        except Exception as exc:
            for record in records:
                self._mark_failed(record, str(exc))
            return len(records), 0, len(records)

        for record in records:
            processed += 1
            downloaded: DownloadedMp4 | None = None
            try:
                self._mark_downloading(record)
                downloaded = self._download(record)
                self._mark_uploading(record, downloaded)
                file_id = self._upload(client, downloaded.path)
                self._mark_success(record, downloaded, file_id)
                completed += 1
            except Exception as exc:
                self._mark_failed(record, str(exc), downloaded=downloaded)
                skipped += 1
                self.logger.warning(
                    "douyin mp4 file upload failed",
                    extra={
                        "record_id": record.record_id,
                        "video_url": record.video_url,
                        "error_text": str(exc),
                    },
                )
            finally:
                if downloaded:
                    _unlink_if_exists(downloaded.path)
                _unlink_if_exists(self._tmp_part_path(record))
        return processed, completed, skipped

    def _download(self, record: Mp4LinkRecord) -> DownloadedMp4:
        url = _download_url(record)
        filename = self._filename(record)
        final_path = self.paths.mp4_upload_tmp_dir / filename
        part_path = self._tmp_part_path(record)
        _unlink_if_exists(final_path)
        _unlink_if_exists(part_path)

        headers = {"User-Agent": DOWNLOAD_UA, "Accept": "video/mp4,video/*,*/*;q=0.8"}
        req = request.Request(url, headers=headers, method="GET")
        try:
            with request.urlopen(req, timeout=60) as response:
                status_code = getattr(response, "status", response.getcode())
                if status_code not in {200, 206}:
                    raise RuntimeError(f"download returned status_code={status_code}")
                content_type = response.headers.get("content-type")
                content_length = response.headers.get("content-length")
                digest = hashlib.sha256()
                downloaded_bytes = 0
                first_bytes = b""
                with part_path.open("wb") as handle:
                    while True:
                        chunk = response.read(1024 * 1024)
                        if not chunk:
                            break
                        if not first_bytes:
                            first_bytes = chunk[:64]
                        downloaded_bytes += len(chunk)
                        if downloaded_bytes > self.run_config.max_bytes:
                            raise RuntimeError(
                                f"download exceeded max_bytes={self.run_config.max_bytes}; downloaded_bytes={downloaded_bytes}"
                            )
                        digest.update(chunk)
                        handle.write(chunk)
        except error.HTTPError as exc:
            raise RuntimeError(f"download returned status_code={exc.code}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"download failed: {exc.reason}") from exc

        if downloaded_bytes <= 0:
            raise RuntimeError("download returned an empty file")
        if not _looks_like_mp4(content_type, first_bytes):
            raise RuntimeError(f"download returned non-video content_type={content_type or 'unknown'}")

        part_path.rename(final_path)
        return DownloadedMp4(
            path=final_path,
            content_type=content_type,
            content_length=content_length,
            downloaded_bytes=downloaded_bytes,
            sha256=digest.hexdigest(),
        )

    def _upload(self, client: Any, path: Path) -> str:
        with path.open("rb") as handle:
            response = client.files.create(file=handle, purpose=self.run_config.file_purpose)
        file_id = getattr(response, "id", None)
        if not file_id and isinstance(response, dict):
            file_id = response.get("id")
        if not file_id:
            raise RuntimeError("Files API response did not include file id")
        return str(file_id)

    def _mark_downloading(self, record: Mp4LinkRecord) -> None:
        existing = self._existing_for(record)
        self.upload_store.upsert(
            Mp4FileUploadRecord(
                record_id=record.record_id,
                workflow_run_id=record.workflow_run_id,
                video_url=record.video_url,
                creator_name=record.creator_name,
                status="downloading",
                direct_mp4_url=record.direct_mp4_url,
                final_url=record.final_url,
                source_mp4_access_mode=record.access_mode,
                file_id=existing.file_id if existing else None,
                file_purpose=self.run_config.file_purpose,
                filename=self._filename(record),
                content_type=existing.content_type if existing else record.content_type,
                content_length=existing.content_length if existing else record.content_length,
                downloaded_bytes=existing.downloaded_bytes if existing else None,
                sha256=existing.sha256 if existing else None,
                attempt_count=(existing.attempt_count if existing else 0) + 1,
                last_error=None,
                updated_at=_utc_now_iso(),
            ),
            key_field="video_url",
        )

    def _mark_uploading(self, record: Mp4LinkRecord, downloaded: DownloadedMp4) -> None:
        existing = self._existing_for(record)
        self.upload_store.upsert(
            Mp4FileUploadRecord(
                record_id=record.record_id,
                workflow_run_id=record.workflow_run_id,
                video_url=record.video_url,
                creator_name=record.creator_name,
                status="uploading",
                direct_mp4_url=record.direct_mp4_url,
                final_url=record.final_url,
                source_mp4_access_mode=record.access_mode,
                file_id=existing.file_id if existing else None,
                file_purpose=self.run_config.file_purpose,
                filename=downloaded.path.name,
                content_type=downloaded.content_type,
                content_length=downloaded.content_length,
                downloaded_bytes=downloaded.downloaded_bytes,
                sha256=downloaded.sha256,
                attempt_count=existing.attempt_count if existing else 1,
                last_error=None,
                updated_at=_utc_now_iso(),
            ),
            key_field="video_url",
        )

    def _mark_success(self, record: Mp4LinkRecord, downloaded: DownloadedMp4, file_id: str) -> None:
        existing = self._existing_for(record)
        self.upload_store.upsert(
            Mp4FileUploadRecord(
                record_id=record.record_id,
                workflow_run_id=record.workflow_run_id,
                video_url=record.video_url,
                creator_name=record.creator_name,
                status="success",
                direct_mp4_url=record.direct_mp4_url,
                final_url=record.final_url,
                source_mp4_access_mode=record.access_mode,
                file_id=file_id,
                file_purpose=self.run_config.file_purpose,
                filename=downloaded.path.name,
                content_type=downloaded.content_type,
                content_length=downloaded.content_length,
                downloaded_bytes=downloaded.downloaded_bytes,
                sha256=downloaded.sha256,
                attempt_count=existing.attempt_count if existing else 1,
                last_error=None,
                updated_at=_utc_now_iso(),
            ),
            key_field="video_url",
        )

    def _mark_failed(self, record: Mp4LinkRecord, error_text: str, downloaded: DownloadedMp4 | None = None) -> None:
        existing = self._existing_for(record)
        self.upload_store.upsert(
            Mp4FileUploadRecord(
                record_id=record.record_id,
                workflow_run_id=record.workflow_run_id,
                video_url=record.video_url,
                creator_name=record.creator_name,
                status="failed",
                direct_mp4_url=record.direct_mp4_url,
                final_url=record.final_url,
                source_mp4_access_mode=record.access_mode,
                file_id=existing.file_id if existing else None,
                file_purpose=self.run_config.file_purpose,
                filename=(downloaded.path.name if downloaded else self._filename(record)),
                content_type=(downloaded.content_type if downloaded else (existing.content_type if existing else record.content_type)),
                content_length=(
                    downloaded.content_length if downloaded else (existing.content_length if existing else record.content_length)
                ),
                downloaded_bytes=downloaded.downloaded_bytes if downloaded else (existing.downloaded_bytes if existing else None),
                sha256=downloaded.sha256 if downloaded else (existing.sha256 if existing else None),
                attempt_count=existing.attempt_count if existing else 1,
                last_error=error_text,
                updated_at=_utc_now_iso(),
            ),
            key_field="video_url",
        )

    def _existing_for(self, record: Mp4LinkRecord) -> Mp4FileUploadRecord | None:
        for existing in self.upload_store.load_all():
            if existing.video_url == record.video_url and (
                not self.run_config.workflow_run_id or existing.workflow_run_id == self.run_config.workflow_run_id
            ):
                return existing
        return None

    def _filename(self, record: Mp4LinkRecord) -> str:
        safe_record_id = "".join(char if char.isalnum() or char in {"-", "_"} else "_" for char in record.record_id)
        return f"{safe_record_id}.mp4"

    def _tmp_part_path(self, record: Mp4LinkRecord) -> Path:
        return self.paths.mp4_upload_tmp_dir / f"{self._filename(record)}.part"


def _is_uploadable_mp4(record: Mp4LinkRecord) -> bool:
    if record.status != "success":
        return False
    if record.access_mode != "external_direct":
        return False
    return bool(_download_url(record))


def _download_url(record: Mp4LinkRecord) -> str:
    return (record.final_url or record.direct_mp4_url or "").strip()


def _looks_like_mp4(content_type: str | None, first_bytes: bytes) -> bool:
    normalized = (content_type or "").lower()
    if normalized.startswith("video/") or "video_mp4" in normalized or "mp4" in normalized:
        return True
    return len(first_bytes) >= 12 and first_bytes[4:8] == b"ftyp"


def _build_ark_client(base_url: str, api_key: str) -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise MissingDependencyError("openai is not installed; run pip install --upgrade 'openai>=1.0'.") from exc
    return OpenAI(base_url=base_url, api_key=api_key)


def _load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(PACKAGE_ROOT / "local_only" / "env" / "search_agent.env")


def _unlink_if_exists(path: Path) -> None:
    try:
        path.unlink()
    except FileNotFoundError:
        return


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()
