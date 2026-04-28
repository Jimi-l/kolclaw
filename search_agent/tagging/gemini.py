from __future__ import annotations

import base64
import json
import mimetypes
import os
from pathlib import Path
from typing import Any
from urllib import error, request

from search_agent.models.analysis import GeminiAnalysisPayload
from search_agent.models.discovery import CreatorDiscoveryRecord


class GeminiContentAnalyzer:
    ENDPOINT_TEMPLATE = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"

    def __init__(self, model_name: str = "gemini-2.5-flash", timeout_seconds: float = 45.0):
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

    def analyze(self, record: CreatorDiscoveryRecord) -> GeminiAnalysisPayload:
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")

        payload = self._build_request_payload(record)
        req = request.Request(
            self.ENDPOINT_TEMPLATE.format(model=self.model_name),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": api_key,
            },
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Gemini API HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Gemini API request failed: {exc.reason}") from exc

        if "error" in response_payload:
            raise RuntimeError(json.dumps(response_payload["error"], ensure_ascii=False))
        text = _extract_candidate_text(response_payload)
        if not text:
            raise RuntimeError("Gemini API returned no structured text")
        return GeminiAnalysisPayload.model_validate_json(text)

    def _build_request_payload(self, record: CreatorDiscoveryRecord) -> dict[str, Any]:
        prompt_sections = [
            "你是一个抖音内容分析助手。请只返回 JSON，不要输出额外说明。",
            "任务目标：基于 KolClaw 内容/商业标签体系，判断内容垂类路径、职业/兴趣/生活/出镜关系标签，以及明确商业合作信号。",
            "要求：",
            "1. 不要沿用旧的 persona/content/scene/ad_fit 思路。",
            "2. 只有在存在明确商业信号时才填写 monetization；否则返回空数组。",
            "3. content_taxonomy_path 最多 4 级，必须按顺序返回。",
            "4. profession_tags / interest_tags / life_tags / appearance_relation_tags 只接受显式证据，不要宽泛联想。",
            f"创作者: {record.creator_name or 'unknown'}",
            f"主页简介: {record.profile_bio or ''}",
            f"近期作品标题: {' | '.join(record.recent_video_titles)}",
            f"推荐流摘要: {record.active_text_summary or ''}",
            f"主标题: {record.video_title_text or ''}",
            f"视频简介: {record.video_description_raw or ''}",
            f"扩展简介: {record.expanded_description_text or ''}",
            f"文本包: {record.video_text_bundle or ''}",
            f"章节文本: {' | '.join(record.chapter_texts)}",
            f"相关搜索: {' | '.join(record.related_search_terms)}",
            f"作者声明: {' | '.join(record.author_statement_texts)}",
            f"可见字幕: {' | '.join(record.visible_subtitle_segments)}",
            f"高赞评论: {' | '.join(_comment_lines(record.top_comments))}",
            f"互动与发布时间: {record.total_interaction_text or ''} {record.publish_time_raw or ''}",
            f"补充说明: {record.notes or ''}",
        ]
        parts: list[dict[str, Any]] = [{"text": "\n".join(section for section in prompt_sections if section.strip())}]
        for image_path in record.keyframe_paths:
            file_path = Path(image_path)
            if not file_path.exists():
                continue
            mime_type = mimetypes.guess_type(file_path.name)[0] or "image/png"
            parts.append(
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": base64.b64encode(file_path.read_bytes()).decode("ascii"),
                    }
                }
            )
        return {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "responseMimeType": "application/json",
                "responseJsonSchema": _analysis_schema(),
            },
        }


def _comment_lines(comments) -> list[str]:
    lines: list[str] = []
    for comment in comments:
        author = f"{comment.author_name}: " if comment.author_name else ""
        lines.append(f"{author}{comment.text}")
    return lines


def _extract_candidate_text(response_payload: dict[str, Any]) -> str | None:
    for candidate in response_payload.get("candidates", []):
        content = candidate.get("content") or {}
        for part in content.get("parts", []):
            text = part.get("text")
            if text:
                return text
    return None


def _analysis_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "video_content_summary": {
                "type": "string",
                "description": "用简洁中文总结视频内容主题、叙事和信息类型。",
            },
            "content_taxonomy_path": {
                "type": "array",
                "items": {"type": "string"},
                "maxItems": 4,
            },
            "content_leaf_tags": {
                "type": "array",
                "items": {"type": "string"},
            },
            "profession_tags": {
                "type": "array",
                "items": {"type": "string"},
            },
            "interest_tags": {
                "type": "array",
                "items": {"type": "string"},
            },
            "life_tags": {
                "type": "array",
                "items": {"type": "string"},
            },
            "appearance_relation_tags": {
                "type": "array",
                "items": {"type": "string"},
            },
            "monetization": {
                "type": "array",
                "items": {"type": "string"},
            },
            "cooperate_type": {
                "type": ["string", "null"],
                "enum": ["图文 / 视频20s", "21-60s", "60s+", None],
            },
            "content_analysis_reasoning": {
                "type": "string",
                "description": "说明内容标签与商业判断的证据来源，优先引用标题、简介、章节、评论和关键帧。",
            },
            "safety_or_uncertainty_note": {
                "type": ["string", "null"],
                "description": "若信息不足或存在噪声，说明不确定点。",
            },
        },
        "required": [
            "video_content_summary",
            "content_taxonomy_path",
            "content_leaf_tags",
            "profession_tags",
            "interest_tags",
            "life_tags",
            "appearance_relation_tags",
            "monetization",
            "cooperate_type",
            "content_analysis_reasoning",
        ],
        "additionalProperties": False,
    }
