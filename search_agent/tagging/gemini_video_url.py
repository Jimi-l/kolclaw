from __future__ import annotations

import json
import os
from urllib import error, request

from search_agent.models.discovery import CreatorDiscoveryRecord
from search_agent.models.video_url_analysis import VideoUrlAnalysisPayload
from search_agent.utils.normalize import normalize_chinese_count


class GeminiVideoUrlAnalyzer:
    def __init__(self, model_name: str = "gemini-3.1-flash", timeout_seconds: float = 90.0):
        self.model_name = model_name
        self.timeout_seconds = timeout_seconds

    def analyze(self, record: CreatorDiscoveryRecord) -> VideoUrlAnalysisPayload:
        api_key = os.getenv("VIDEO_ANALYSIS_API_KEY") or os.getenv("OPENAI_API_KEY") or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("VIDEO_ANALYSIS_API_KEY or OPENAI_API_KEY is not set")

        base_url = os.getenv("VIDEO_ANALYSIS_BASE_URL") or os.getenv("OPENAI_BASE_URL")
        if not base_url:
            raise RuntimeError("VIDEO_ANALYSIS_BASE_URL or OPENAI_BASE_URL is not set")

        endpoint = base_url.rstrip("/")
        if not endpoint.endswith("/chat/completions"):
            endpoint = f"{endpoint}/chat/completions"

        payload = self._build_request_payload(record)
        req = request.Request(
            endpoint,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
            },
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        )
        try:
            with request.urlopen(req, timeout=self.timeout_seconds) as response:
                response_payload = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Video analysis API HTTP {exc.code}: {detail}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Video analysis API request failed: {exc.reason}") from exc

        text = _extract_choice_text(response_payload)
        if not text:
            raise RuntimeError("Video analysis API returned no structured content")
        try:
            return VideoUrlAnalysisPayload.model_validate_json(text)
        except Exception:
            return VideoUrlAnalysisPayload.model_validate(_extract_json_object(text))

    def _build_request_payload(self, record: CreatorDiscoveryRecord) -> dict:
        share_count = normalize_chinese_count(record.share_count_raw)
        follower_count = record.follower_count_normalized or normalize_chinese_count(record.follower_count_raw)
        user_prompt = "\n".join(
            [
                "请严格输出 JSON，不要输出 markdown、解释或额外前后缀。",
                "你是一个抖音视频爆款分析助手。你需要优先分析 video_url 对应的视频；如果你无法直接访问该视频内容，请结合我提供的评论、字幕、标题、简介、互动数据做 metadata_only 分析，并在 video_access_status 标明。",
                f"video_url: {record.video_url}",
                "",
                "先执行这个确定性爆款规则，并在后续分析中沿用这个规则，不要自行改阈值：",
                "1. 转发量 > 10万，则一定是爆款。",
                "2. 否则如果转发量 > 1万，并且账号粉丝 < 30万，则判定这条是爆款。",
                "3. 其他情况不直接按规则判爆款，但仍需分析内容潜力。",
                f"当前已知转发量: {record.share_count_raw or '未知'}（标准化后: {share_count if share_count is not None else '未知'}）",
                f"当前已知粉丝量: {record.follower_count_raw or '未知'}（标准化后: {follower_count if follower_count is not None else '未知'}）",
                "",
                "请围绕以下问题分析：",
                "1. 主题是什么？",
                "2. 用什么样的人（主角）在什么场景上，做了一个什么事情？事情有什么特点？遇到了什么样的人？这个人有没有故事特点？",
                "3. 人物在画面上有什么看点？",
                "4. 综合视频内容、评论区、弹幕/字幕，判断这条视频的可复制性。尤其判断是否因为主角过高颜值、特殊人物设定、特殊道具、特殊故事导致不可复制。",
                "5. 给这条视频打内容标签，例如爱情、vlog、东北、旅行、冬天、游戏、舞蹈、颜值等；可以多标签。",
                "6. 用户为什么一直不划走？点赞、评论、收藏、转发的主要原因分别是什么？特别关注前五秒是否有争议行为、美女、帅哥、反差、悬念等吸睛元素。",
                "7. 观众的情绪是怎样的？分别分析开头、中段、看完后的情绪。",
                "8. 核心受众是什么人群？年龄、性别、收入水平、地域/城市等级偏好是什么？要结合“不划走原因”和评论内容来推断。",
                "9. 如果可复制性低，分析这个达人沿用同样剧本/延续剧情，是否仍会引起粉丝兴趣。",
                "",
                "你可用的补充上下文如下：",
                f"创作者: {record.creator_name or '未知'}",
                f"主页简介: {record.profile_bio or ''}",
                f"推荐流摘要: {record.active_text_summary or ''}",
                f"标题: {record.video_title_text or ''}",
                f"视频简介: {record.video_description_raw or ''}",
                f"扩展简介: {record.expanded_description_text or ''}",
                f"文本包: {record.video_text_bundle or ''}",
                f"章节文本: {' | '.join(record.chapter_texts)}",
                f"相关搜索: {' | '.join(record.related_search_terms)}",
                f"作者声明: {' | '.join(record.author_statement_texts)}",
                f"可见字幕: {' | '.join(record.visible_subtitle_segments)}",
                f"高赞评论: {' | '.join(_comment_lines(record))}",
                f"互动数据: 点赞={record.like_count_raw or ''} 评论={record.comment_count_raw or ''} 收藏={record.favorite_count_raw or ''} 转发={record.share_count_raw or ''}",
                f"发布时间: {record.publish_time_raw or ''}",
                f"补充备注: {record.notes or ''}",
            ]
        )
        return {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "你是一个严格按要求返回 JSON 的短视频分析助手。"
                        "如果无法直接读取链接视频，也必须结合提供的元数据完成尽可能可靠的分析。"
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.2,
            "response_format": {
                "type": "json_schema",
                "json_schema": {
                    "name": "douyin_video_url_analysis",
                    "strict": True,
                    "schema": _analysis_schema(),
                },
            },
        }


def _comment_lines(record: CreatorDiscoveryRecord) -> list[str]:
    lines: list[str] = []
    for comment in record.top_comments[:5]:
        author = f"{comment.author_name}: " if comment.author_name else ""
        lines.append(f"{author}{comment.text}")
    return lines


def _extract_choice_text(response_payload: dict) -> str | None:
    for choice in response_payload.get("choices", []):
        message = choice.get("message") or {}
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content
    return None


def _extract_json_object(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise RuntimeError("Response does not contain a JSON object")
    return json.loads(text[start : end + 1])


def _analysis_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "video_access_status": {"type": "string", "enum": ["accessible", "metadata_only", "uncertain"]},
            "theme": {"type": "string"},
            "protagonist": {"type": "string"},
            "scene": {"type": "string"},
            "core_action": {"type": "string"},
            "action_highlights": {"type": "array", "items": {"type": "string"}},
            "encountered_people": {"type": "array", "items": {"type": "string"}},
            "people_story_traits": {"type": "array", "items": {"type": "string"}},
            "visual_highlights": {"type": "array", "items": {"type": "string"}},
            "tags": {"type": "array", "items": {"type": "string"}},
            "retention_reasons": {"type": "array", "items": {"type": "string"}},
            "interaction_reasons": {"type": "array", "items": {"type": "string"}},
            "opening_hook_analysis": {"type": "string"},
            "audience_emotion": {
                "type": "object",
                "properties": {
                    "opening": {"type": "string"},
                    "middle": {"type": "string"},
                    "ending": {"type": "string"},
                },
                "required": ["opening", "middle", "ending"],
                "additionalProperties": False,
            },
            "core_audience": {
                "type": "object",
                "properties": {
                    "age_bands": {"type": "array", "items": {"type": "string"}},
                    "gender_skew": {"type": ["string", "null"]},
                    "income_level": {"type": ["string", "null"]},
                    "city_tier_preference": {"type": "array", "items": {"type": "string"}},
                    "region_preference": {"type": "array", "items": {"type": "string"}},
                    "reasoning": {"type": ["string", "null"]},
                },
                "required": [
                    "age_bands",
                    "gender_skew",
                    "income_level",
                    "city_tier_preference",
                    "region_preference",
                    "reasoning",
                ],
                "additionalProperties": False,
            },
            "replicability": {"type": "string", "enum": ["高", "中", "低"]},
            "replicability_reasoning": {"type": "string"},
            "series_continuation_interest": {"type": "string"},
            "analysis_reasoning": {"type": "string"},
        },
        "required": [
            "video_access_status",
            "theme",
            "protagonist",
            "scene",
            "core_action",
            "action_highlights",
            "encountered_people",
            "people_story_traits",
            "visual_highlights",
            "tags",
            "retention_reasons",
            "interaction_reasons",
            "opening_hook_analysis",
            "audience_emotion",
            "core_audience",
            "replicability",
            "replicability_reasoning",
            "series_continuation_interest",
            "analysis_reasoning",
        ],
        "additionalProperties": False,
    }
