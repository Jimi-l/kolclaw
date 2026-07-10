from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from search_agent.artifacts import ArtifactManager
from search_agent.config import (
    BrowserConfig,
    DiscoveryRunConfig,
    DouyinVerticalRunConfig,
    DoubaoVideoAnalysisRunConfig,
    DouyinLiveWorkflowRunConfig,
    DouyinVideoPipelineRunConfig,
    EnrichmentRunConfig,
    Mp4FileUploadRunConfig,
    Mp4LinkRunConfig,
    RuntimePaths,
    VideoUrlAnalysisRunConfig,
)
from search_agent.enums import WorkflowStage
from search_agent.exceptions import BlockingStateError, MissingDependencyError, SearchAgentError
from search_agent.logging_utils import configure_logging, get_logger


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="search_agent")
    subparsers = parser.add_subparsers(dest="command", required=True)

    discovery = subparsers.add_parser("creator-discovery", help="Run Douyin creator discovery.")
    discovery.add_argument("--headless", action="store_true", help="Run the browser headlessly.")
    discovery.add_argument("--max-records", type=int, default=10, help="Stop after this many qualified records.")
    discovery.add_argument("--max-minutes", type=int, default=20, help="Maximum runtime in minutes.")
    discovery.add_argument("--max-candidates", type=int, default=100, help="Maximum feed items to inspect.")
    discovery.add_argument(
        "--bootstrap-login",
        action="store_true",
        help="Bootstrap the persisted Douyin session until the recommend feed is interactable, then exit. This does not run the homepage/scroll browse loop.",
    )
    discovery.add_argument("--discovery-output", type=str, help="Optional JSONL output path for discovery records.")
    discovery.add_argument("--queue-output", type=str, help="Optional JSONL queue path for Xingtu candidates.")
    discovery.add_argument("--artifacts-dir", type=str, help="Optional artifacts root override.")
    discovery.add_argument("--browser-channel", type=str, default=None, help="Optional browser channel, e.g. chrome.")
    discovery.add_argument(
        "--disable-content-analysis",
        action="store_true",
        help="Skip the automatic Gemini/heuristic content-analysis stage after discovery.",
    )
    discovery.add_argument(
        "--analysis-model",
        type=str,
        default="gemini-2.5-flash",
        help="Gemini model name used for the automatic content-analysis stage.",
    )
    discovery.add_argument(
        "--analysis-keyframes",
        type=int,
        default=4,
        help="Maximum number of keyframe screenshots to capture for each saved discovery record.",
    )
    discovery.add_argument(
        "--analysis-max-items",
        type=int,
        default=None,
        help="Optional cap for how many newly queued discovery records are analyzed after discovery.",
    )
    discovery.add_argument("--log-level", type=str, default="INFO", help="Logging level.")

    vertical_discovery = subparsers.add_parser(
        "douyin-vertical-discovery",
        help="Run Douyin tag-based vertical discovery from a CSV tag table.",
    )
    vertical_discovery.add_argument("--headless", action="store_true", help="Run the browser headlessly.")
    vertical_discovery.add_argument("--max-records", type=int, default=100, help="Stop after this many qualified records.")
    vertical_discovery.add_argument("--max-minutes", type=int, default=20, help="Maximum runtime in minutes.")
    vertical_discovery.add_argument("--max-candidates", type=int, default=100, help="Maximum tags to inspect.")
    vertical_discovery.add_argument(
        "--tag-table",
        type=str,
        help="CSV path with serial number and tag name columns. Defaults to adapters/douyin_vertical/tag_table.csv.",
    )
    vertical_discovery.add_argument(
        "--per-tag-minutes",
        type=float,
        default=3.0,
        help="Maximum time budget for each tag before moving to the next tag.",
    )
    vertical_discovery.add_argument(
        "--per-tag-records",
        type=int,
        default=None,
        help="Optional cap for how many qualified records to save for each tag before moving to the next tag.",
    )
    vertical_discovery.add_argument(
        "--publish-filter",
        type=str,
        default="一周内",
        help="Douyin search publish-time filter to select after opening 筛选.",
    )
    vertical_discovery.add_argument(
        "--search-without-hash",
        action="store_true",
        help="Strip leading # from each tag before typing/searching.",
    )
    vertical_discovery.add_argument(
        "--tag-cooldown-min-seconds",
        type=float,
        default=8.0,
        help="Minimum cooldown between tags to reduce Douyin search-rate pressure.",
    )
    vertical_discovery.add_argument(
        "--tag-cooldown-max-seconds",
        type=float,
        default=18.0,
        help="Maximum cooldown between tags to reduce Douyin search-rate pressure.",
    )
    vertical_discovery.add_argument(
        "--pressure-cooldown-min-seconds",
        type=float,
        default=45.0,
        help="Minimum cooldown after sparse results, skipped tags, captcha, or SMS pressure.",
    )
    vertical_discovery.add_argument(
        "--pressure-cooldown-max-seconds",
        type=float,
        default=90.0,
        help="Maximum cooldown after sparse results, skipped tags, captcha, or SMS pressure.",
    )
    vertical_discovery.add_argument(
        "--disable-jingxuan-url-repair",
        action="store_true",
        help="Do not force Douyin search result pages back to /jingxuan/search/ before opening result cards.",
    )
    vertical_discovery.add_argument("--discovery-output", type=str, help="Optional JSONL output path for discovery records.")
    vertical_discovery.add_argument("--queue-output", type=str, help="Optional JSONL queue path for Xingtu candidates.")
    vertical_discovery.add_argument("--artifacts-dir", type=str, help="Optional artifacts root override.")
    vertical_discovery.add_argument("--browser-channel", type=str, default=None, help="Optional browser channel, e.g. chrome.")
    vertical_discovery.add_argument(
        "--disable-content-analysis",
        action="store_true",
        help="Skip the automatic Gemini/heuristic content-analysis stage after discovery.",
    )
    vertical_discovery.add_argument(
        "--analysis-model",
        type=str,
        default="gemini-2.5-flash",
        help="Gemini model name used for the automatic content-analysis stage.",
    )
    vertical_discovery.add_argument(
        "--analysis-keyframes",
        type=int,
        default=4,
        help="Maximum number of keyframe screenshots to capture for each saved discovery record.",
    )
    vertical_discovery.add_argument(
        "--analysis-max-items",
        type=int,
        default=None,
        help="Optional cap for how many newly queued discovery records are analyzed after discovery.",
    )
    vertical_discovery.add_argument("--log-level", type=str, default="INFO", help="Logging level.")

    enrichment = subparsers.add_parser("xingtu-enrichment", help="Run Xingtu enrichment on queued records.")
    enrichment.add_argument("--headless", action="store_true", help="Run the browser headlessly.")
    enrichment.add_argument("--max-items", type=int, default=50, help="Maximum queued records to process.")
    enrichment.add_argument("--queue-input", type=str, help="Optional JSONL queue input path.")
    enrichment.add_argument("--enrichment-output", type=str, help="Optional JSONL output path for enrichment records.")
    enrichment.add_argument("--artifacts-dir", type=str, help="Optional artifacts root override.")
    enrichment.add_argument("--browser-channel", type=str, default=None, help="Optional browser channel, e.g. chrome.")
    enrichment.add_argument("--log-level", type=str, default="INFO", help="Logging level.")

    video_url_analysis = subparsers.add_parser(
        "video-url-analysis",
        help="Analyze discovered Douyin videos by video_url with Gemini and write a separate JSONL result file.",
    )
    video_url_analysis.add_argument(
        "--discovery-input",
        type=str,
        help="Optional JSONL input path for discovery records. Defaults to runtime/data/discovery_records.jsonl.",
    )
    video_url_analysis.add_argument(
        "--output",
        type=str,
        help="Optional JSONL output path for video-url analysis. Defaults to runtime/data/video_url_analysis.jsonl.",
    )
    video_url_analysis.add_argument(
        "--model",
        type=str,
        default="gemini-3.1-flash",
        help="Model name for the video-url analysis request.",
    )
    video_url_analysis.add_argument(
        "--max-items",
        type=int,
        default=None,
        help="Optional cap for how many unique video_url records to analyze.",
    )
    video_url_analysis.add_argument(
        "--force",
        action="store_true",
        help="Re-analyze video_url items even if they already exist in the output JSONL.",
    )
    video_url_analysis.add_argument("--artifacts-dir", type=str, help="Optional artifacts root override.")
    video_url_analysis.add_argument("--log-level", type=str, default="INFO", help="Logging level.")

    mp4_links = subparsers.add_parser(
        "douyin-mp4-links",
        help="Resolve discovered Douyin video_url values into direct MP4 URLs.",
    )
    mp4_links.add_argument("--headless", action="store_true", help="Run the browser headlessly.")
    mp4_links.add_argument(
        "--discovery-input",
        type=str,
        help="Optional JSONL input path for discovery records. Defaults to runtime/data/discovery_records.jsonl.",
    )
    mp4_links.add_argument(
        "--output",
        type=str,
        help="Optional JSONL output path for MP4 links. Defaults to runtime/data/mp4_links.jsonl.",
    )
    mp4_links.add_argument("--batch-size", type=int, default=10, help="Number of pending video URLs to process per batch.")
    mp4_links.add_argument("--flush-seconds", type=float, default=60.0, help="Watch-mode tail batch flush interval.")
    mp4_links.add_argument("--watch", action="store_true", help="Keep scanning for new discovery records.")
    mp4_links.add_argument("--poll-seconds", type=float, default=5.0, help="Watch-mode scan interval.")
    mp4_links.add_argument("--force", action="store_true", help="Re-resolve URLs even if they already succeeded.")
    mp4_links.add_argument("--retry-failed", action="store_true", help="Retry failed or stuck processing records.")
    mp4_links.add_argument("--max-batches", type=int, default=None, help="Optional watch-mode batch cap.")
    mp4_links.add_argument("--page-wait-ms", type=int, default=8_000, help="Milliseconds to collect network responses after navigation.")
    mp4_links.add_argument("--artifacts-dir", type=str, help="Optional artifacts root override.")
    mp4_links.add_argument("--browser-channel", type=str, default=None, help="Optional browser channel, e.g. chrome.")
    mp4_links.add_argument("--log-level", type=str, default="INFO", help="Logging level.")

    mp4_files = subparsers.add_parser(
        "douyin-mp4-files",
        help="Download resolved direct MP4 URLs and upload them to Ark Files API.",
    )
    mp4_files.add_argument(
        "--mp4-links-input",
        type=str,
        help="Optional JSONL input path for MP4 links. Defaults to runtime/data/mp4_links.jsonl.",
    )
    mp4_files.add_argument(
        "--output",
        type=str,
        help="Optional JSONL output path for uploaded files. Defaults to runtime/data/mp4_file_uploads.jsonl.",
    )
    mp4_files.add_argument("--batch-size", type=int, default=10, help="Number of pending MP4 files to upload per batch.")
    mp4_files.add_argument("--flush-seconds", type=float, default=60.0, help="Watch-mode tail batch flush interval.")
    mp4_files.add_argument("--watch", action="store_true", help="Keep scanning for newly resolved MP4 links.")
    mp4_files.add_argument("--poll-seconds", type=float, default=5.0, help="Watch-mode scan interval.")
    mp4_files.add_argument("--force", action="store_true", help="Re-upload even if a file_id already exists.")
    mp4_files.add_argument("--retry-failed", action="store_true", help="Retry failed or stuck upload records.")
    mp4_files.add_argument("--max-batches", type=int, default=None, help="Optional watch-mode batch cap.")
    mp4_files.add_argument("--max-bytes", type=int, default=524_288_000, help="Maximum MP4 download size in bytes.")
    mp4_files.add_argument(
        "--ark-base-url",
        type=str,
        default="https://ark.cn-beijing.volces.com/api/v3",
        help="Ark OpenAI-compatible API base URL.",
    )
    mp4_files.add_argument("--file-purpose", type=str, default="user_data", help="Files API purpose value.")
    mp4_files.add_argument("--artifacts-dir", type=str, help="Optional artifacts root override.")
    mp4_files.add_argument("--log-level", type=str, default="INFO", help="Logging level.")

    doubao_video_analysis = subparsers.add_parser(
        "douyin-doubao-video-analysis",
        help="Analyze uploaded Douyin MP4 file_ids with Doubao-Seed-2.0-lite.",
    )
    doubao_video_analysis.add_argument(
        "--mp4-files-input",
        type=str,
        help="Optional JSONL input path for uploaded MP4 files. Defaults to runtime/data/mp4_file_uploads.jsonl.",
    )
    doubao_video_analysis.add_argument(
        "--discovery-input",
        type=str,
        help="Optional JSONL input path for discovery context. Defaults to runtime/data/discovery_records.jsonl.",
    )
    doubao_video_analysis.add_argument(
        "--output",
        type=str,
        help="Optional JSONL output path for Doubao analysis. Defaults to runtime/data/doubao_video_analysis.jsonl.",
    )
    doubao_video_analysis.add_argument("--batch-size", type=int, default=10, help="Number of uploaded videos to analyze per batch.")
    doubao_video_analysis.add_argument("--flush-seconds", type=float, default=60.0, help="Watch-mode tail batch flush interval.")
    doubao_video_analysis.add_argument("--watch", action="store_true", help="Keep scanning for newly uploaded file_ids.")
    doubao_video_analysis.add_argument("--poll-seconds", type=float, default=5.0, help="Watch-mode scan interval.")
    doubao_video_analysis.add_argument("--force", action="store_true", help="Re-analyze even if a completed record exists.")
    doubao_video_analysis.add_argument("--retry-failed", action="store_true", help="Retry failed or stuck analysis records.")
    doubao_video_analysis.add_argument("--max-batches", type=int, default=None, help="Optional watch-mode batch cap.")
    doubao_video_analysis.add_argument(
        "--model",
        type=str,
        default="doubao-seed-2-0-lite-260215",
        help="Doubao model name for video analysis.",
    )
    doubao_video_analysis.add_argument(
        "--ark-base-url",
        type=str,
        default="https://ark.cn-beijing.volces.com/api/v3",
        help="Ark OpenAI-compatible API base URL.",
    )
    doubao_video_analysis.add_argument("--max-output-tokens", type=int, default=4096, help="Maximum output tokens for analysis.")
    doubao_video_analysis.add_argument("--artifacts-dir", type=str, help="Optional artifacts root override.")
    doubao_video_analysis.add_argument("--log-level", type=str, default="INFO", help="Logging level.")

    video_pipeline = subparsers.add_parser(
        "douyin-video-pipeline",
        help="Run MP4 link resolving, Files upload, and Doubao video analysis until a target count is reached.",
    )
    video_pipeline.add_argument(
        "--discovery-input",
        type=str,
        help="Optional JSONL input path for discovery records. Defaults to runtime/data/discovery_records.jsonl.",
    )
    video_pipeline.add_argument(
        "--mp4-links-output",
        type=str,
        help="Optional JSONL output path for MP4 links. Defaults to runtime/data/mp4_links.jsonl.",
    )
    video_pipeline.add_argument(
        "--mp4-files-output",
        type=str,
        help="Optional JSONL output path for uploaded files. Defaults to runtime/data/mp4_file_uploads.jsonl.",
    )
    video_pipeline.add_argument(
        "--analysis-output",
        type=str,
        help="Optional JSONL output path for Doubao analysis. Defaults to runtime/data/doubao_video_analysis.jsonl.",
    )
    video_pipeline.add_argument("--target-completed", type=int, default=10, help="Stop after this many completed Doubao analyses.")
    video_pipeline.add_argument("--batch-size", type=int, default=10, help="Batch size passed to each pipeline stage.")
    video_pipeline.add_argument("--max-rounds", type=int, default=10, help="Maximum full pipeline rounds to run.")
    video_pipeline.add_argument("--retry-failed", action=argparse.BooleanOptionalAction, default=True, help="Retry failed or stuck records.")
    video_pipeline.add_argument("--force", action="store_true", help="Force reprocessing of already successful records.")
    video_pipeline.add_argument("--headless", action=argparse.BooleanOptionalAction, default=True, help="Run the browser headlessly.")
    video_pipeline.add_argument("--browser-channel", type=str, default="chrome", help="Optional browser channel, e.g. chrome.")
    video_pipeline.add_argument("--page-wait-ms", type=int, default=8_000, help="Milliseconds to collect MP4 network responses.")
    video_pipeline.add_argument("--poll-seconds", type=float, default=5.0, help="Reserved poll interval for future watch-style pipeline runs.")
    video_pipeline.add_argument(
        "--ark-base-url",
        type=str,
        default="https://ark.cn-beijing.volces.com/api/v3",
        help="Ark OpenAI-compatible API base URL.",
    )
    video_pipeline.add_argument(
        "--model",
        type=str,
        default="doubao-seed-2-0-lite-260215",
        help="Doubao model name for video analysis.",
    )
    video_pipeline.add_argument("--max-output-tokens", type=int, default=4096, help="Maximum output tokens for analysis.")
    video_pipeline.add_argument("--artifacts-dir", type=str, help="Optional artifacts root override.")
    video_pipeline.add_argument("--log-level", type=str, default="INFO", help="Logging level.")

    live_workflow = subparsers.add_parser(
        "douyin-live-workflow",
        help="Run a product-style live workflow from fresh Douyin discovery through Doubao video analysis.",
    )
    live_workflow.add_argument("--target-completed", type=int, default=10, help="Stop after this many completed analyses for this run.")
    live_workflow.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Live workflow gate size. Defaults to 5: discover 5 videos, then start one-by-one downstream processing.",
    )
    live_workflow.add_argument(
        "--stage-item-batch-size",
        type=int,
        default=1,
        help="How many items each downstream stage processes per pass after the gate is met.",
    )
    live_workflow.add_argument("--watch", action="store_true", help="Keep running until max-minutes or user interruption.")
    live_workflow.add_argument("--retry-failed", action=argparse.BooleanOptionalAction, default=True, help="Retry failed or stuck records.")
    live_workflow.add_argument(
        "--headless",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="Run the browser headlessly. Live workflow defaults to a visible Chrome window for captcha/popup recovery.",
    )
    live_workflow.add_argument("--browser-channel", type=str, default="chrome", help="Optional browser channel, e.g. chrome.")
    live_workflow.add_argument("--max-minutes", type=int, default=30, help="Maximum live workflow runtime in minutes.")
    live_workflow.add_argument(
        "--max-discovery-records",
        type=int,
        default=None,
        help="Maximum new discovery records for this run. Defaults to target-completed * discovery-multiplier.",
    )
    live_workflow.add_argument(
        "--discovery-multiplier",
        type=int,
        default=3,
        help="Discovery oversampling multiplier used when max-discovery-records is not set.",
    )
    live_workflow.add_argument("--max-discovery-candidates", type=int, default=100, help="Maximum feed items to inspect in discovery.")
    live_workflow.add_argument("--page-wait-ms", type=int, default=8_000, help="Milliseconds to collect MP4 network responses.")
    live_workflow.add_argument("--poll-seconds", type=float, default=5.0, help="Polling interval between live workflow checks.")
    live_workflow.add_argument("--stalled-round-limit", type=int, default=5, help="Stop after this many no-progress rounds once discovery ends.")
    live_workflow.add_argument(
        "--ark-base-url",
        type=str,
        default="https://ark.cn-beijing.volces.com/api/v3",
        help="Ark OpenAI-compatible API base URL.",
    )
    live_workflow.add_argument(
        "--model",
        type=str,
        default="doubao-seed-2-0-lite-260215",
        help="Doubao model name for video analysis.",
    )
    live_workflow.add_argument("--max-output-tokens", type=int, default=4096, help="Maximum output tokens for analysis.")
    live_workflow.add_argument("--artifacts-dir", type=str, help="Optional artifacts root override.")
    live_workflow.add_argument("--log-level", type=str, default="INFO", help="Logging level.")
    return parser


def build_paths(args: argparse.Namespace) -> RuntimePaths:
    paths = RuntimePaths.defaults()
    project_root = paths.project_root

    def resolve(path_value: str) -> Path:
        path = Path(path_value)
        return path if path.is_absolute() else project_root / path

    if getattr(args, "artifacts_dir", None):
        paths.artifacts_dir = resolve(args.artifacts_dir)
    if getattr(args, "discovery_output", None):
        paths.discovery_output = resolve(args.discovery_output)
    if getattr(args, "queue_output", None):
        paths.queue_output = resolve(args.queue_output)
    if getattr(args, "queue_input", None):
        paths.queue_output = resolve(args.queue_input)
    if getattr(args, "enrichment_output", None):
        paths.enrichment_output = resolve(args.enrichment_output)
    if getattr(args, "discovery_input", None):
        paths.discovery_output = resolve(args.discovery_input)
    if getattr(args, "mp4_links_input", None):
        paths.mp4_links_output = resolve(args.mp4_links_input)
    if getattr(args, "mp4_files_input", None):
        paths.mp4_file_uploads_output = resolve(args.mp4_files_input)
    if getattr(args, "mp4_links_output", None):
        paths.mp4_links_output = resolve(args.mp4_links_output)
    if getattr(args, "mp4_files_output", None):
        paths.mp4_file_uploads_output = resolve(args.mp4_files_output)
    if getattr(args, "analysis_output", None):
        paths.doubao_video_analysis_output = resolve(args.analysis_output)
    if getattr(args, "output", None):
        if getattr(args, "command", None) == "douyin-mp4-links":
            paths.mp4_links_output = resolve(args.output)
        elif getattr(args, "command", None) == "douyin-mp4-files":
            paths.mp4_file_uploads_output = resolve(args.output)
        elif getattr(args, "command", None) == "douyin-doubao-video-analysis":
            paths.doubao_video_analysis_output = resolve(args.output)
        else:
            paths.video_url_analysis_output = resolve(args.output)
    paths.ensure_directories()
    return paths


def _emit_summary(payload: dict, exit_code: int) -> int:
    stream = sys.stdout if exit_code == 0 else sys.stderr
    print(json.dumps(payload, ensure_ascii=False, indent=2), file=stream)
    return exit_code


def run_creator_discovery(args: argparse.Namespace) -> int:
    from search_agent.adapters.douyin.workflow import CreatorDiscoveryWorkflow

    paths = build_paths(args)
    artifacts = ArtifactManager.create(paths.artifacts_dir, WorkflowStage.CREATOR_DISCOVERY)
    configure_logging(artifacts.log_path, args.log_level)
    logger = get_logger("search_agent.cli")
    logger.info("starting creator-discovery", extra={"run_id": artifacts.run_id})

    workflow = CreatorDiscoveryWorkflow(
        paths=paths,
        artifacts=artifacts,
        browser_config=BrowserConfig(
            site_name="douyin",
            headless=args.headless,
            channel=args.browser_channel,
        ),
        run_config=DiscoveryRunConfig(
            max_records=args.max_records,
            max_minutes=args.max_minutes,
            max_candidates=args.max_candidates,
            bootstrap_login=args.bootstrap_login,
            content_analysis_enabled=not args.disable_content_analysis,
            analysis_model=args.analysis_model,
            analysis_keyframes=args.analysis_keyframes,
            analysis_max_items=args.analysis_max_items,
        ),
    )
    if args.bootstrap_login:
        summary = workflow.bootstrap_login()
        return _emit_summary(summary, 0)
    summary = workflow.run()
    return _emit_summary(summary.model_dump(mode="json"), 0)


def run_douyin_vertical_discovery(args: argparse.Namespace) -> int:
    from search_agent.adapters.douyin_vertical.vertical_workflow import DouyinVerticalDiscoveryWorkflow

    paths = build_paths(args)
    project_root = paths.project_root

    def resolve_optional(path_value: str | None) -> Path | None:
        if not path_value:
            return None
        path = Path(path_value)
        return path if path.is_absolute() else project_root / path

    artifacts = ArtifactManager.create(paths.artifacts_dir, WorkflowStage.DOUYIN_VERTICAL_DISCOVERY)
    configure_logging(artifacts.log_path, args.log_level)
    logger = get_logger("search_agent.cli")
    logger.info("starting douyin-vertical-discovery", extra={"run_id": artifacts.run_id})

    workflow = DouyinVerticalDiscoveryWorkflow(
        paths=paths,
        artifacts=artifacts,
        browser_config=BrowserConfig(
            site_name="douyin_vertical",
            headless=args.headless,
            channel=args.browser_channel,
        ),
        run_config=DouyinVerticalRunConfig(
            max_records=args.max_records,
            max_minutes=args.max_minutes,
            max_candidates=args.max_candidates,
            tag_table_path=resolve_optional(args.tag_table),
            per_tag_minutes=args.per_tag_minutes,
            per_tag_records=args.per_tag_records,
            search_publish_filter=args.publish_filter,
            include_hash_in_search=not args.search_without_hash,
            tag_cooldown_min_seconds=args.tag_cooldown_min_seconds,
            tag_cooldown_max_seconds=args.tag_cooldown_max_seconds,
            pressure_cooldown_min_seconds=args.pressure_cooldown_min_seconds,
            pressure_cooldown_max_seconds=args.pressure_cooldown_max_seconds,
            force_jingxuan_search_url=not args.disable_jingxuan_url_repair,
            content_analysis_enabled=not args.disable_content_analysis,
            analysis_model=args.analysis_model,
            analysis_keyframes=args.analysis_keyframes,
            analysis_max_items=args.analysis_max_items,
        ),
    )
    summary = workflow.run()
    return _emit_summary(summary.model_dump(mode="json"), 0)


def run_xingtu_enrichment(args: argparse.Namespace) -> int:
    from search_agent.adapters.xingtu.workflow import XingtuEnrichmentWorkflow

    paths = build_paths(args)
    artifacts = ArtifactManager.create(paths.artifacts_dir, WorkflowStage.XINGTU_ENRICHMENT)
    configure_logging(artifacts.log_path, args.log_level)
    logger = get_logger("search_agent.cli")
    logger.info("starting xingtu-enrichment", extra={"run_id": artifacts.run_id})

    workflow = XingtuEnrichmentWorkflow(
        paths=paths,
        artifacts=artifacts,
        browser_config=BrowserConfig(
            site_name="xingtu",
            headless=args.headless,
            channel=args.browser_channel,
        ),
        run_config=EnrichmentRunConfig(max_items=args.max_items),
    )
    summary = workflow.run()
    return _emit_summary(summary.model_dump(mode="json"), 0)


def run_video_url_analysis(args: argparse.Namespace) -> int:
    from search_agent.adapters.douyin.video_url_analysis import VideoUrlAnalysisWorkflow

    paths = build_paths(args)
    artifacts = ArtifactManager.create(paths.artifacts_dir, WorkflowStage.VIDEO_URL_ANALYSIS)
    configure_logging(artifacts.log_path, args.log_level)
    logger = get_logger("search_agent.cli")
    logger.info("starting video-url-analysis", extra={"run_id": artifacts.run_id})

    workflow = VideoUrlAnalysisWorkflow(
        paths=paths,
        artifacts=artifacts,
        run_config=VideoUrlAnalysisRunConfig(
            model_name=args.model,
            max_items=args.max_items,
            force=args.force,
        ),
    )
    summary = workflow.run()
    return _emit_summary(summary.model_dump(mode="json"), 0)


def run_douyin_mp4_links(args: argparse.Namespace) -> int:
    from search_agent.adapters.douyin.mp4_links import DouyinMp4LinkWorkflow

    paths = build_paths(args)
    artifacts = ArtifactManager.create(paths.artifacts_dir, WorkflowStage.DOUYIN_MP4_LINKS)
    configure_logging(artifacts.log_path, args.log_level)
    logger = get_logger("search_agent.cli")
    logger.info("starting douyin-mp4-links", extra={"run_id": artifacts.run_id})

    workflow = DouyinMp4LinkWorkflow(
        paths=paths,
        artifacts=artifacts,
        browser_config=BrowserConfig(
            site_name="douyin",
            headless=args.headless,
            channel=args.browser_channel,
        ),
        run_config=Mp4LinkRunConfig(
            batch_size=args.batch_size,
            flush_seconds=args.flush_seconds,
            watch=args.watch,
            poll_seconds=args.poll_seconds,
            force=args.force,
            retry_failed=args.retry_failed,
            max_batches=args.max_batches,
            page_wait_ms=args.page_wait_ms,
        ),
    )
    summary = workflow.run()
    return _emit_summary(summary.model_dump(mode="json"), 0)


def run_douyin_mp4_files(args: argparse.Namespace) -> int:
    from search_agent.adapters.douyin.mp4_file_uploads import DouyinMp4FileUploadWorkflow

    paths = build_paths(args)
    artifacts = ArtifactManager.create(paths.artifacts_dir, WorkflowStage.DOUYIN_MP4_FILES)
    configure_logging(artifacts.log_path, args.log_level)
    logger = get_logger("search_agent.cli")
    logger.info("starting douyin-mp4-files", extra={"run_id": artifacts.run_id})

    workflow = DouyinMp4FileUploadWorkflow(
        paths=paths,
        artifacts=artifacts,
        run_config=Mp4FileUploadRunConfig(
            batch_size=args.batch_size,
            flush_seconds=args.flush_seconds,
            watch=args.watch,
            poll_seconds=args.poll_seconds,
            force=args.force,
            retry_failed=args.retry_failed,
            max_batches=args.max_batches,
            max_bytes=args.max_bytes,
            ark_base_url=args.ark_base_url,
            file_purpose=args.file_purpose,
        ),
    )
    summary = workflow.run()
    return _emit_summary(summary.model_dump(mode="json"), 0)


def run_douyin_doubao_video_analysis(args: argparse.Namespace) -> int:
    from search_agent.adapters.douyin.doubao_video_analysis import DoubaoVideoAnalysisWorkflow

    paths = build_paths(args)
    artifacts = ArtifactManager.create(paths.artifacts_dir, WorkflowStage.DOUYIN_DOUBAO_VIDEO_ANALYSIS)
    configure_logging(artifacts.log_path, args.log_level)
    logger = get_logger("search_agent.cli")
    logger.info("starting douyin-doubao-video-analysis", extra={"run_id": artifacts.run_id})

    workflow = DoubaoVideoAnalysisWorkflow(
        paths=paths,
        artifacts=artifacts,
        run_config=DoubaoVideoAnalysisRunConfig(
            batch_size=args.batch_size,
            flush_seconds=args.flush_seconds,
            watch=args.watch,
            poll_seconds=args.poll_seconds,
            force=args.force,
            retry_failed=args.retry_failed,
            max_batches=args.max_batches,
            model_name=args.model,
            ark_base_url=args.ark_base_url,
            max_output_tokens=args.max_output_tokens,
        ),
    )
    summary = workflow.run()
    return _emit_summary(summary.model_dump(mode="json"), 0)


def run_douyin_video_pipeline(args: argparse.Namespace) -> int:
    from search_agent.adapters.douyin.video_pipeline import DouyinVideoPipelineWorkflow

    paths = build_paths(args)
    artifacts = ArtifactManager.create(paths.artifacts_dir, WorkflowStage.DOUYIN_VIDEO_PIPELINE)
    configure_logging(artifacts.log_path, args.log_level)
    logger = get_logger("search_agent.cli")
    logger.info("starting douyin-video-pipeline", extra={"run_id": artifacts.run_id})

    workflow = DouyinVideoPipelineWorkflow(
        paths=paths,
        artifacts=artifacts,
        run_config=DouyinVideoPipelineRunConfig(
            target_completed=args.target_completed,
            batch_size=args.batch_size,
            max_rounds=args.max_rounds,
            retry_failed=args.retry_failed,
            force=args.force,
            headless=args.headless,
            browser_channel=args.browser_channel,
            page_wait_ms=args.page_wait_ms,
            poll_seconds=args.poll_seconds,
            ark_base_url=args.ark_base_url,
            model_name=args.model,
            max_output_tokens=args.max_output_tokens,
        ),
    )
    summary = workflow.run()
    return _emit_summary(summary, int(summary.get("exit_code", 1)))


def run_douyin_live_workflow(args: argparse.Namespace) -> int:
    from search_agent.adapters.douyin.live_workflow import DouyinLiveWorkflow

    paths = build_paths(args)
    artifacts = ArtifactManager.create(paths.artifacts_dir, WorkflowStage.DOUYIN_LIVE_WORKFLOW)
    configure_logging(artifacts.log_path, args.log_level)
    logger = get_logger("search_agent.cli")
    logger.info("starting douyin-live-workflow", extra={"run_id": artifacts.run_id})

    workflow = DouyinLiveWorkflow(
        paths=paths,
        artifacts=artifacts,
        run_config=DouyinLiveWorkflowRunConfig(
            target_completed=args.target_completed,
            batch_size=args.batch_size,
            stage_item_batch_size=args.stage_item_batch_size,
            watch=args.watch,
            retry_failed=args.retry_failed,
            headless=args.headless,
            browser_channel=args.browser_channel,
            max_minutes=args.max_minutes,
            max_discovery_records=args.max_discovery_records,
            discovery_multiplier=args.discovery_multiplier,
            max_discovery_candidates=args.max_discovery_candidates,
            page_wait_ms=args.page_wait_ms,
            poll_seconds=args.poll_seconds,
            stalled_round_limit=args.stalled_round_limit,
            ark_base_url=args.ark_base_url,
            model_name=args.model,
            max_output_tokens=args.max_output_tokens,
        ),
    )
    summary = workflow.run()
    return _emit_summary(summary, int(summary.get("exit_code", 1)))


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "creator-discovery":
            return run_creator_discovery(args)
        if args.command == "douyin-vertical-discovery":
            return run_douyin_vertical_discovery(args)
        if args.command == "xingtu-enrichment":
            return run_xingtu_enrichment(args)
        if args.command == "video-url-analysis":
            return run_video_url_analysis(args)
        if args.command == "douyin-mp4-links":
            return run_douyin_mp4_links(args)
        if args.command == "douyin-mp4-files":
            return run_douyin_mp4_files(args)
        if args.command == "douyin-doubao-video-analysis":
            return run_douyin_doubao_video_analysis(args)
        if args.command == "douyin-video-pipeline":
            return run_douyin_video_pipeline(args)
        if args.command == "douyin-live-workflow":
            return run_douyin_live_workflow(args)
        parser.error(f"Unsupported command: {args.command}")
    except BlockingStateError as exc:
        return _emit_summary(
            {
                "status": "blocked",
                "reason": exc.reason.value,
                "message": exc.message,
                "page_name": exc.page_name,
                "page_state": exc.page_state,
                "screenshot_path": exc.screenshot_path,
                "required_user_action": exc.required_user_action,
                "needs_user_action": exc.needs_user_action,
                "resumable": exc.resumable,
            },
            2,
        )
    except MissingDependencyError as exc:
        return _emit_summary({"status": "error", "message": str(exc)}, 3)
    except SearchAgentError as exc:
        return _emit_summary({"status": "error", "message": str(exc)}, 1)
