from __future__ import annotations

import json
import logging
import os
import time
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from search_agent.artifacts import ArtifactManager
from search_agent.config import DoubaoVideoAnalysisRunConfig, PACKAGE_ROOT, RuntimePaths
from search_agent.enums import WorkflowStage
from search_agent.exceptions import MissingDependencyError
from search_agent.models.common import RunSummary
from search_agent.models.discovery import CreatorDiscoveryRecord
from search_agent.models.doubao_video_analysis import DoubaoVideoAnalysisRecord
from search_agent.models.mp4_file_uploads import Mp4FileUploadRecord
from search_agent.storage.jsonl_store import JsonlStore
from search_agent.utils.normalize import normalize_chinese_count


ArkClientFactory = Callable[[str, str], Any]


class DoubaoVideoAnalysisResult:
    def __init__(self, payload: dict, raw_response_text: str, response_id: str | None):
        self.payload = payload
        self.raw_response_text = raw_response_text
        self.response_id = response_id


class DoubaoVideoAnalyzer:
    def __init__(
        self,
        client: Any,
        model_name: str,
        temperature: float = 0.2,
        max_output_tokens: int | None = 4096,
    ) -> None:
        self.client = client
        self.model_name = model_name
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

    def analyze(self, upload: Mp4FileUploadRecord, discovery: CreatorDiscoveryRecord | None) -> DoubaoVideoAnalysisResult:
        prompt = build_doubao_video_prompt(upload, discovery)
        request_payload = {
            "model": self.model_name,
            "input": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_video",
                            "file_id": upload.file_id,
                        },
                        {"type": "input_text", "text": prompt},
                    ],
                }
            ],
            "temperature": self.temperature,
        }
        if self.max_output_tokens is not None:
            request_payload["max_output_tokens"] = self.max_output_tokens

        try:
            response = self.client.responses.create(
                **request_payload,
                text={"format": {"type": "json_schema", "name": "doubao_video_analysis", "strict": True, "schema": _analysis_schema()}},
            )
        except Exception as exc:
            if not _looks_like_schema_compat_error(exc):
                raise
            response = self.client.responses.create(**request_payload)

        raw_text = _extract_response_text(response)
        if not raw_text:
            raise RuntimeError("Doubao response did not include text output")
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError:
            payload = _extract_json_object(raw_text)
        return DoubaoVideoAnalysisResult(
            payload=payload,
            raw_response_text=raw_text,
            response_id=getattr(response, "id", None),
        )


class DoubaoVideoAnalysisWorkflow:
    def __init__(
        self,
        paths: RuntimePaths,
        artifacts: ArtifactManager,
        run_config: DoubaoVideoAnalysisRunConfig,
        client_factory: ArkClientFactory | None = None,
        analyzer_factory: Callable[[Any, DoubaoVideoAnalysisRunConfig], Any] | None = None,
    ) -> None:
        self.paths = paths
        self.artifacts = artifacts
        self.run_config = run_config
        self.logger = logging.getLogger("search_agent.doubao_video_analysis")
        self.upload_store = JsonlStore(self.paths.mp4_file_uploads_output, Mp4FileUploadRecord)
        self.discovery_store = JsonlStore(self.paths.discovery_output, CreatorDiscoveryRecord)
        self.analysis_store = JsonlStore(self.paths.doubao_video_analysis_output, DoubaoVideoAnalysisRecord)
        self.client_factory = client_factory or _build_ark_client
        self.analyzer_factory = analyzer_factory or _build_analyzer

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
            stage=WorkflowStage.DOUYIN_DOUBAO_VIDEO_ANALYSIS,
            run_id=self.artifacts.run_id,
            duration_minutes=duration_minutes,
            processed_candidates=processed,
            successful_records=completed,
            skipped_items=skipped,
            blocked_items=blocked,
            next_stage_ready=completed,
            output_path=str(self.paths.doubao_video_analysis_output),
            queue_path=None,
        )

    def _pending_records(self) -> list[Mp4FileUploadRecord]:
        latest_by_url: dict[str, Mp4FileUploadRecord] = {}
        for record in self.upload_store.load_all():
            if self.run_config.workflow_run_id and record.workflow_run_id != self.run_config.workflow_run_id:
                continue
            if record.status != "success" or not record.file_id:
                continue
            latest_by_url[record.video_url] = record

        existing_by_url = {
            record.video_url: record
            for record in self.analysis_store.load_all()
            if not self.run_config.workflow_run_id or record.workflow_run_id == self.run_config.workflow_run_id
        }
        pending: list[Mp4FileUploadRecord] = []
        for video_url, record in latest_by_url.items():
            existing = existing_by_url.get(video_url)
            if self._should_skip_existing(existing):
                continue
            pending.append(record)
        return pending

    def _should_skip_existing(self, existing: DoubaoVideoAnalysisRecord | None) -> bool:
        if existing is None or self.run_config.force:
            return False
        if existing.status == "completed":
            return True
        if existing.status == "failed" and not self.run_config.retry_failed:
            return True
        if existing.status == "processing" and not self.run_config.retry_failed:
            return True
        return False

    def _process_batch(self, uploads: list[Mp4FileUploadRecord]) -> tuple[int, int, int]:
        if not uploads:
            return 0, 0, 0

        api_key = os.getenv("ARK_API_KEY")
        if not api_key:
            for upload in uploads:
                self._mark_failed(upload, "ARK_API_KEY is not set; put it in search_agent/local_only/env/search_agent.env or export it.")
            return len(uploads), 0, len(uploads)

        discovery_by_url = {
            record.video_url: record
            for record in self.discovery_store.load_all()
            if record.video_url and (not self.run_config.workflow_run_id or record.workflow_run_id == self.run_config.workflow_run_id)
        }
        try:
            client = self.client_factory(self.run_config.ark_base_url, api_key)
            analyzer = self.analyzer_factory(client, self.run_config)
        except Exception as exc:
            for upload in uploads:
                self._mark_failed(upload, str(exc))
            return len(uploads), 0, len(uploads)

        processed = completed = skipped = 0
        for upload in uploads:
            processed += 1
            discovery = discovery_by_url.get(upload.video_url)
            try:
                self._mark_processing(upload)
                result = analyzer.analyze(upload, discovery)
                self._mark_completed(upload, result)
                completed += 1
            except Exception as exc:
                self._mark_failed(upload, str(exc))
                skipped += 1
                self.logger.warning(
                    "doubao video analysis failed",
                    extra={
                        "record_id": upload.record_id,
                        "video_url": upload.video_url,
                        "file_id": upload.file_id,
                        "error_text": str(exc),
                    },
                )
        return processed, completed, skipped

    def _mark_processing(self, upload: Mp4FileUploadRecord) -> None:
        existing = self._existing_for(upload)
        self.analysis_store.upsert(
            DoubaoVideoAnalysisRecord(
                record_id=upload.record_id,
                workflow_run_id=upload.workflow_run_id,
                video_url=upload.video_url,
                creator_name=upload.creator_name,
                file_id=upload.file_id or "",
                status="processing",
                analysis_model=self.run_config.model_name,
                response_id=existing.response_id if existing else None,
                raw_response_text=existing.raw_response_text if existing else None,
                attempt_count=(existing.attempt_count if existing else 0) + 1,
                last_error=None,
                updated_at=_utc_now_iso(),
            ),
            key_field="video_url",
        )

    def _mark_completed(self, upload: Mp4FileUploadRecord, result: DoubaoVideoAnalysisResult) -> None:
        existing = self._existing_for(upload)
        payload = result.payload
        self.analysis_store.upsert(
            DoubaoVideoAnalysisRecord(
                record_id=upload.record_id,
                workflow_run_id=upload.workflow_run_id,
                video_url=upload.video_url,
                creator_name=upload.creator_name,
                file_id=upload.file_id or "",
                status="completed",
                analysis_model=self.run_config.model_name,
                response_id=result.response_id,
                is_viral=payload.get("is_viral"),
                viral_rule_hit=payload.get("viral_rule_hit"),
                viral_rule_reasoning=payload.get("viral_rule_reasoning"),
                theme=payload.get("theme"),
                protagonist=payload.get("protagonist"),
                scene=payload.get("scene"),
                core_action=payload.get("core_action"),
                story_traits=_list_of_strings(payload.get("story_traits")),
                visual_hooks=_list_of_strings(payload.get("visual_hooks")),
                replicability=payload.get("replicability"),
                replicability_reasoning=payload.get("replicability_reasoning"),
                tags=_list_of_strings(payload.get("tags")),
                retention_reasons=_list_of_strings(payload.get("retention_reasons")),
                interaction_reasons=_list_of_strings(payload.get("interaction_reasons")),
                opening_hook_analysis=payload.get("opening_hook_analysis"),
                audience_emotion=payload.get("audience_emotion") if isinstance(payload.get("audience_emotion"), dict) else {},
                core_audience=payload.get("core_audience") if isinstance(payload.get("core_audience"), dict) else {},
                series_continuation_interest=payload.get("series_continuation_interest"),
                analysis_reasoning=payload.get("analysis_reasoning"),
                raw_response_text=result.raw_response_text,
                attempt_count=existing.attempt_count if existing else 1,
                last_error=None,
                updated_at=_utc_now_iso(),
            ),
            key_field="video_url",
        )

    def _mark_failed(self, upload: Mp4FileUploadRecord, error_text: str) -> None:
        existing = self._existing_for(upload)
        self.analysis_store.upsert(
            DoubaoVideoAnalysisRecord(
                record_id=upload.record_id,
                workflow_run_id=upload.workflow_run_id,
                video_url=upload.video_url,
                creator_name=upload.creator_name,
                file_id=upload.file_id or "",
                status="failed",
                analysis_model=self.run_config.model_name,
                response_id=existing.response_id if existing else None,
                raw_response_text=existing.raw_response_text if existing else None,
                attempt_count=existing.attempt_count if existing else 1,
                last_error=error_text,
                updated_at=_utc_now_iso(),
            ),
            key_field="video_url",
        )

    def _existing_for(self, upload: Mp4FileUploadRecord) -> DoubaoVideoAnalysisRecord | None:
        for existing in self.analysis_store.load_all():
            if existing.video_url == upload.video_url and (
                not self.run_config.workflow_run_id or existing.workflow_run_id == self.run_config.workflow_run_id
            ):
                return existing
        return None


def build_doubao_video_prompt(upload: Mp4FileUploadRecord, record: CreatorDiscoveryRecord | None) -> str:
    share_count = normalize_chinese_count(record.share_count_raw) if record else None
    follower_count = (record.follower_count_normalized or normalize_chinese_count(record.follower_count_raw)) if record else None
    return "\n".join(
        [
            "请严格输出 JSON，不要输出 markdown、解释或额外前后缀。",
            "你正在分析一个已经通过 Files API 上传的视频文件。请优先观看并理解 file_id 对应的视频内容，再结合我提供的抖音采集上下文做爆款分析。",
            f"file_id: {upload.file_id or '未知'}",
            f"video_url: {upload.video_url}",
            "",
            "先执行这个确定性爆款规则，不要自行改阈值：",
            "1. 转发量 > 10万，则一定是爆款。",
            "2. 否则如果转发量 > 1万，并且账号粉丝 < 30万，则判定这条是爆款。",
            "3. 其他情况不直接按规则判爆款，但仍需结合视频内容、评论区、字幕/弹幕线索分析内容潜力。",
            f"当前已知转发量: {_value(record.share_count_raw if record else None)}（标准化后: {share_count if share_count is not None else '未知'}）",
            f"当前已知粉丝量: {_value(record.follower_count_raw if record else None)}（标准化后: {follower_count if follower_count is not None else '未知'}）",
            "",
            "请分析：这条视频的主题是什么；用什么样的人（主角）在什么场景上，做了一个什么事情；事情有什么特点；遇到了什么样的人；这个人有没有故事特点。",
            "请分析：人物在画面上有什么看点；可以同时分析视频内容、评论区、弹幕或字幕，特别是弹幕/字幕特别集中的时间段用户在关注什么。",
            "请综合判断可复制性：是否因为主角过高颜值导致内容观看度高；是否因为特殊故事情况、特殊人物形象、特殊道具导致普通人难以复制；普通人能否同样获得这些条件。",
            "请给内容标签，例如爱情、vlog、东北、旅行、冬天、游戏、舞蹈、颜值等，可以多标签。",
            "请分析用户一直观看（不划走）的原因，以及点赞、评论、收藏、转发的主要原因。重点考虑前五秒是否出现争议性行为、美女、帅哥、反差、悬念等吸引眼光和好奇心的元素。",
            "请分析观众情绪：分别从开头、过程中、看完后的情况分析。",
            "请分析核心受众画像：年龄、性别、收入水平、地域或城市等级偏好。需要从用户为什么不划走、观众想看的痛点（vs 自身现实的区别）、弹幕、评论区内容推断；要区分能明显辨别观众人群的评论线索。",
            "如果可复制性低，请分析这个达人用同样剧本延续剧情，是否仍会引起粉丝兴趣。",
            "",
            "你可用的抖音采集上下文如下：",
            f"创作者: {_value(record.creator_name if record else upload.creator_name)}",
            f"主页简介: {_value(record.profile_bio if record else None)}",
            f"推荐流摘要: {_value(record.active_text_summary if record else None)}",
            f"标题: {_value(record.video_title_text if record else None)}",
            f"视频简介: {_value(record.video_description_raw if record else None)}",
            f"扩展简介: {_value(record.expanded_description_text if record else None)}",
            f"文本包: {_value(record.video_text_bundle if record else None)}",
            f"章节文本: {_join(record.chapter_texts if record else [])}",
            f"相关搜索: {_join(record.related_search_terms if record else [])}",
            f"作者声明: {_join(record.author_statement_texts if record else [])}",
            f"可见字幕: {_join(record.visible_subtitle_segments if record else [])}",
            f"高赞评论: {_join(_comment_lines(record) if record else [])}",
            f"互动数据: 点赞={_value(record.like_count_raw if record else None)} 评论={_value(record.comment_count_raw if record else None)} 收藏={_value(record.favorite_count_raw if record else None)} 转发={_value(record.share_count_raw if record else None)}",
            f"发布时间: {_value(record.publish_time_raw if record else None)}",
            f"补充备注: {_value(record.notes if record else None)}",
            "",
            "JSON 字段必须包含：is_viral, viral_rule_hit, viral_rule_reasoning, theme, protagonist, scene, core_action, story_traits, visual_hooks, replicability, replicability_reasoning, tags, retention_reasons, interaction_reasons, opening_hook_analysis, audience_emotion, core_audience, series_continuation_interest, analysis_reasoning。",
        ]
    )


def _analysis_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "is_viral": {"type": "boolean"},
            "viral_rule_hit": {"type": "string"},
            "viral_rule_reasoning": {"type": "string"},
            "theme": {"type": "string"},
            "protagonist": {"type": "string"},
            "scene": {"type": "string"},
            "core_action": {"type": "string"},
            "story_traits": {"type": "array", "items": {"type": "string"}},
            "visual_hooks": {"type": "array", "items": {"type": "string"}},
            "replicability": {"type": "string"},
            "replicability_reasoning": {"type": "string"},
            "tags": {"type": "array", "items": {"type": "string"}},
            "retention_reasons": {"type": "array", "items": {"type": "string"}},
            "interaction_reasons": {"type": "array", "items": {"type": "string"}},
            "opening_hook_analysis": {"type": "string"},
            "audience_emotion": {"type": "object"},
            "core_audience": {"type": "object"},
            "series_continuation_interest": {"type": "string"},
            "analysis_reasoning": {"type": "string"},
        },
        "required": [
            "is_viral",
            "viral_rule_hit",
            "viral_rule_reasoning",
            "theme",
            "protagonist",
            "scene",
            "core_action",
            "story_traits",
            "visual_hooks",
            "replicability",
            "replicability_reasoning",
            "tags",
            "retention_reasons",
            "interaction_reasons",
            "opening_hook_analysis",
            "audience_emotion",
            "core_audience",
            "series_continuation_interest",
            "analysis_reasoning",
        ],
        "additionalProperties": False,
    }


def _build_ark_client(base_url: str, api_key: str) -> Any:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise MissingDependencyError("openai is not installed; run pip install --upgrade 'openai>=1.0'.") from exc
    return OpenAI(base_url=base_url, api_key=api_key)


def _build_analyzer(client: Any, run_config: DoubaoVideoAnalysisRunConfig) -> DoubaoVideoAnalyzer:
    return DoubaoVideoAnalyzer(
        client=client,
        model_name=run_config.model_name,
        temperature=run_config.temperature,
        max_output_tokens=run_config.max_output_tokens,
    )


def _load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(PACKAGE_ROOT / "local_only" / "env" / "search_agent.env")


def _extract_response_text(response: Any) -> str | None:
    output_text = getattr(response, "output_text", None)
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()
    if isinstance(response, dict):
        output_text = response.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text.strip()
        output = response.get("output", [])
    else:
        output = getattr(response, "output", [])
    for item in output or []:
        content = item.get("content", []) if isinstance(item, dict) else getattr(item, "content", [])
        for part in content or []:
            text = part.get("text") if isinstance(part, dict) else getattr(part, "text", None)
            if isinstance(text, str) and text.strip():
                return text.strip()
    return None


def _extract_json_object(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise RuntimeError("Doubao response does not contain a JSON object")
    return json.loads(text[start : end + 1])


def _looks_like_schema_compat_error(exc: Exception) -> bool:
    text = str(exc).lower()
    return any(token in text for token in ("json_schema", "response_format", "text.format", "unsupported", "schema"))


def _list_of_strings(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value if str(item).strip()]


def _comment_lines(record: CreatorDiscoveryRecord) -> list[str]:
    lines: list[str] = []
    for comment in record.top_comments[:10]:
        author = f"{comment.author_name}: " if comment.author_name else ""
        lines.append(f"{author}{comment.text}")
    return lines


def _join(values: list[str]) -> str:
    return " | ".join(item for item in values if item) or "未知"


def _value(value: str | None) -> str:
    return value if value else "未知"


def _utc_now_iso() -> str:
    return datetime.now(UTC).isoformat()
