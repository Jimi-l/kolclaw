from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


PACKAGE_ROOT = Path(__file__).resolve().parent


@dataclass(slots=True)
class RuntimePaths:
    project_root: Path
    artifacts_dir: Path
    runtime_dir: Path
    browser_state_dir: Path
    discovery_output: Path
    queue_output: Path
    enrichment_output: Path
    analysis_queue_output: Path
    analysis_output: Path
    video_url_analysis_output: Path
    mp4_links_output: Path
    mp4_file_uploads_output: Path
    doubao_video_analysis_output: Path
    mp4_upload_tmp_dir: Path

    @classmethod
    def defaults(cls, project_root: Path | None = None) -> "RuntimePaths":
        root = project_root or PACKAGE_ROOT
        runtime_dir = root / "runtime"
        return cls(
            project_root=root,
            artifacts_dir=runtime_dir / "artifacts",
            runtime_dir=runtime_dir,
            browser_state_dir=runtime_dir / "browser_state",
            discovery_output=runtime_dir / "data" / "discovery_records.jsonl",
            queue_output=runtime_dir / "queues" / "xingtu_queue.jsonl",
            enrichment_output=runtime_dir / "data" / "xingtu_enrichment.jsonl",
            analysis_queue_output=runtime_dir / "queues" / "content_analysis_queue.jsonl",
            analysis_output=runtime_dir / "data" / "content_analysis.jsonl",
            video_url_analysis_output=runtime_dir / "data" / "video_url_analysis.jsonl",
            mp4_links_output=runtime_dir / "data" / "mp4_links.jsonl",
            mp4_file_uploads_output=runtime_dir / "data" / "mp4_file_uploads.jsonl",
            doubao_video_analysis_output=runtime_dir / "data" / "doubao_video_analysis.jsonl",
            mp4_upload_tmp_dir=runtime_dir / "tmp" / "mp4_uploads",
        )

    def ensure_directories(self) -> None:
        for path in (
            self.artifacts_dir,
            self.runtime_dir,
            self.browser_state_dir,
            self.discovery_output.parent,
            self.queue_output.parent,
            self.enrichment_output.parent,
            self.analysis_queue_output.parent,
            self.analysis_output.parent,
            self.video_url_analysis_output.parent,
            self.mp4_links_output.parent,
            self.mp4_file_uploads_output.parent,
            self.doubao_video_analysis_output.parent,
            self.mp4_upload_tmp_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


@dataclass(slots=True)
class BrowserConfig:
    site_name: str
    headless: bool = False
    timeout_ms: int = 12_000
    slow_mo_ms: int = 0
    channel: str | None = None


@dataclass(slots=True)
class DiscoveryRunConfig:
    max_records: int = 10
    max_minutes: int = 20
    max_candidates: int = 100
    bootstrap_login: bool = False
    content_analysis_enabled: bool = True
    analysis_model: str = "gemini-2.5-flash"
    analysis_keyframes: int = 4
    analysis_max_items: int | None = None
    workflow_run_id: str | None = None
    stop_event: Any | None = None


@dataclass(slots=True)
class EnrichmentRunConfig:
    max_items: int = 50
    min_query_interval_seconds: float = 1.5
    max_query_interval_seconds: float = 3.0


@dataclass(slots=True)
class ContentAnalysisRunConfig:
    enabled: bool = True
    max_items: int | None = None
    keyframe_count: int = 4
    model_name: str = "gemini-2.5-flash"


@dataclass(slots=True)
class VideoUrlAnalysisRunConfig:
    model_name: str = "gemini-3.1-flash"
    max_items: int | None = None
    force: bool = False


@dataclass(slots=True)
class Mp4LinkRunConfig:
    batch_size: int = 10
    flush_seconds: float = 60.0
    watch: bool = False
    poll_seconds: float = 5.0
    force: bool = False
    retry_failed: bool = False
    max_batches: int | None = None
    page_wait_ms: int = 8_000
    workflow_run_id: str | None = None


@dataclass(slots=True)
class Mp4FileUploadRunConfig:
    batch_size: int = 10
    flush_seconds: float = 60.0
    watch: bool = False
    poll_seconds: float = 5.0
    force: bool = False
    retry_failed: bool = False
    max_batches: int | None = None
    max_bytes: int = 524_288_000
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    file_purpose: str = "user_data"
    workflow_run_id: str | None = None


@dataclass(slots=True)
class DoubaoVideoAnalysisRunConfig:
    batch_size: int = 10
    flush_seconds: float = 60.0
    watch: bool = False
    poll_seconds: float = 5.0
    force: bool = False
    retry_failed: bool = False
    max_batches: int | None = None
    model_name: str = "doubao-seed-2-0-lite-260215"
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    temperature: float = 0.2
    max_output_tokens: int | None = 4096
    workflow_run_id: str | None = None


@dataclass(slots=True)
class DouyinVideoPipelineRunConfig:
    target_completed: int = 10
    batch_size: int = 10
    max_rounds: int = 10
    retry_failed: bool = True
    force: bool = False
    headless: bool = True
    browser_channel: str | None = "chrome"
    page_wait_ms: int = 8_000
    poll_seconds: float = 5.0
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    model_name: str = "doubao-seed-2-0-lite-260215"
    max_output_tokens: int | None = 4096


@dataclass(slots=True)
class DouyinLiveWorkflowRunConfig:
    target_completed: int = 10
    batch_size: int = 5
    stage_item_batch_size: int = 1
    watch: bool = False
    retry_failed: bool = True
    headless: bool = False
    browser_channel: str | None = "chrome"
    max_minutes: int = 30
    max_discovery_records: int | None = None
    discovery_multiplier: int = 3
    max_discovery_candidates: int = 100
    page_wait_ms: int = 8_000
    poll_seconds: float = 5.0
    stalled_round_limit: int = 5
    ark_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"
    model_name: str = "doubao-seed-2-0-lite-260215"
    max_output_tokens: int | None = 4096
