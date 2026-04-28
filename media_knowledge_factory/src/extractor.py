from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

from .constants import (
    CHANNEL_TYPE,
    CHUNK_TYPES,
    COMMON_NOISE_MESSAGES,
    EPISODE_GOALS,
    KNOWLEDGE_BASES,
    MANUAL_PLAYBOOK_STEPS,
    MANUAL_TALK_TEMPLATES,
    OBJECTION_TYPES,
    PLATFORM,
    SCHEMA_VERSION,
    SFT_BUCKETS,
    WORKFLOW_STAGES,
)
from .schemas import (
    BriefCard,
    ConversationMessage,
    CreatorTraitEvidence,
    NegotiationEpisode,
    RetrievalChunk,
    TalkTemplate,
    WorkflowPlaybookStep,
)
from .utils import dedupe_keep_order, list_json_files, load_json, mask_sensitive_content, normalize_text, short_hash


NUMBERED_ITEM_PATTERN = re.compile(r"^(?:\d+[、.．]|[-*])")
AMOUNT_TOKEN_PATTERN = re.compile(r"[¥￥]?\d+(?:\.\d+)?\s*(?:[wW万])?")
PERCENT_PATTERN = re.compile(r"(\d+(?:\.\d+)?)\s*[%％]")

BRIEF_MARKERS = ["合作需求", "【合作需求】", "需求：", "合作平台", "品牌：", "【请确认以下】", "【以下请确认】", "以下请确认", "请确认以下"]
QUOTE_MARKERS = ["报价", "返点", "水下", "保量", "制作周期", "一口价", "刊例价", "私单", "星图"]
RIGHTS_MARKERS = ["分发", "授权", "二创", "二剪", "投流", "合作码", "置顶", "保留", "不更新", "评论区", "挂评论区", "脚本"]
PRICE_NEGOTIATION_MARKERS = ["核价", "便宜", "优惠", "折扣", "改价", "报价贵", "服务费", "利润", "太贵"]
REBATE_MARKERS = ["返点", "返", "反点"]
SCHEDULE_MARKERS = ["档期", "几号", "发布", "留档", "锁档", "定金", "制作周期", "最快", "排期"]
CONFIRM_MARKERS = ["确认合作", "确认", "咱们确认合作", "合作哦", "锁档合作"]
DOC_MARKERS = ["入库", "营业执照", "开户地址", "开户行", "账号", "税号", "邮箱", "身份证", "对公", "对私", "发票", "收款"]
PAYMENT_MARKERS = ["付款", "请款", "尾款", "定金", "下单", "支付", "打款", "充值", "财务"]
EXECUTION_MARKERS = ["拉群", "执行", "脚本", "制作", "修改", "发票", "推进", "交付"]
REVISION_MARKERS = ["改稿", "修改", "重拍", "脚本", "贴片"]
DATA_MARKERS = ["数据", "播放", "维护", "千川", "抖加", "跑的不行", "保量", "互动"]
REBATE_RECOVERY_MARKERS = ["返点回收", "返点打款", "返点到账", "返点什么时候", "返点安排", "返点回款", "返点收款"]
REPEAT_MARKERS = ["下次多合作", "后续其他合作", "后面跟", "再有合作"]
CONTACT_MARKERS = ["我通过了你的朋友验证请求", "现在我们可以开始聊天了"]
COLD_OUTREACH_MARKERS = ["你好", "您好", "合作", "方便", "可看下需求"]
LIMIT_MARKERS = ["不接受", "不能", "不行", "改不了", "没法", "只能", "不保", "不一定", "不免费"]

RISKY_TEMPLATE_MARKERS = ["太不变通", "急死了", "说实话", "真是急死了"]


class MediaKnowledgeExtractor:
    def load_conversation_messages(self, input_dir: str | Path) -> tuple[list[ConversationMessage], list[dict]]:
        messages: list[ConversationMessage] = []
        conversations: list[dict] = []

        for file_path in list_json_files(input_dir):
            raw_data = load_json(file_path)
            conversation_messages, metadata = self._build_conversation_messages(raw_data, file_path)
            messages.extend(conversation_messages)
            conversations.append(metadata)

        return messages, conversations

    def _build_conversation_messages(
        self,
        raw_data: dict,
        file_path: Path,
    ) -> tuple[list[ConversationMessage], dict]:
        session = raw_data.get("session", {})
        raw_messages = raw_data.get("messages", [])

        creator_code = normalize_text(session.get("remark") or file_path.stem)
        creator_name = normalize_text(session.get("displayName") or session.get("nickname") or creator_code)
        creator_aliases = dedupe_keep_order([creator_code, creator_name, file_path.stem.replace(".json", "")])
        creator_id = f"creator_{short_hash('|'.join(creator_aliases))}"

        media_display_names = [
            normalize_text(m.get("senderDisplayName"))
            for m in raw_messages
            if m.get("isSend") == 1 and normalize_text(m.get("senderDisplayName"))
        ]
        media_name = Counter(media_display_names).most_common(1)[0][0] if media_display_names else "unknown_media"
        media_id = f"media_{short_hash(media_name)}"

        conversation_id = f"conversation_{short_hash(file_path.name + creator_id + media_id)}"
        conversation_title = f"{creator_code}__{creator_name}"

        conversation_messages: list[ConversationMessage] = []
        for idx, raw_message in enumerate(raw_messages, start=1):
            raw_text = str(raw_message.get("content") or "")
            clean_text = mask_sensitive_content(raw_text)
            role = "agency" if raw_message.get("isSend") == 1 else "creator"
            message_id = f"{conversation_id}_msg_{idx:04d}"
            timestamp = int(raw_message.get("createTime") or 0)
            formatted_time = str(raw_message.get("formattedTime") or "")
            source_ref = {
                "schema_version": SCHEMA_VERSION,
                "source_file": file_path.name,
                "seq_num": idx,
                "local_id": raw_message.get("localId"),
                "platform_message_id": raw_message.get("platformMessageId"),
            }
            evidence_span = {
                "source": "message",
                "seq_num": idx,
                "char_start": 0,
                "char_end": len(raw_text),
            }

            conversation_messages.append(
                ConversationMessage(
                    message_id=message_id,
                    conversation_id=conversation_id,
                    platform=PLATFORM,
                    channel_type=CHANNEL_TYPE,
                    creator_id=creator_id,
                    creator_aliases=creator_aliases,
                    media_id=media_id,
                    media_name=media_name,
                    role=role,
                    raw_text=raw_text,
                    clean_text=clean_text,
                    timestamp=timestamp,
                    formatted_time=formatted_time,
                    source_refs=[source_ref],
                    evidence_span=evidence_span,
                    source_file=file_path.name,
                    conversation_title=conversation_title,
                    seq_num=idx,
                )
            )

        metadata = {
            "conversation_id": conversation_id,
            "creator_id": creator_id,
            "creator_code": creator_code,
            "creator_name": creator_name,
            "creator_aliases": creator_aliases,
            "media_id": media_id,
            "media_name": media_name,
            "source_file": file_path.name,
        }
        return conversation_messages, metadata

    def extract_brief_cards(self, messages: list[ConversationMessage]) -> list[BriefCard]:
        brief_cards: list[BriefCard] = []

        for message in messages:
            if message.role != "agency":
                continue
            if not self._looks_like_brief_delivery(message.clean_text):
                continue

            brief_card = BriefCard(
                brief_card_id=f"brief_{short_hash(message.message_id + message.clean_text)}",
                conversation_id=message.conversation_id,
                creator_id=message.creator_id,
                knowledge_base="brief_framework",
                source_message_id=message.message_id,
                source_message_ids=[message.message_id],
                platform=self._extract_platform_value(message.clean_text),
                brand=self._extract_brand(message.clean_text),
                product=self._extract_product(message.clean_text),
                deliverable_type=self._extract_deliverable_type(message.clean_text),
                content_direction=self._extract_content_direction(message.clean_text),
                schedule_window=self._extract_schedule_window(message.clean_text),
                rights_requirements=self._extract_lines_with_keywords(message.clean_text, RIGHTS_MARKERS),
                distribution_requirements=self._extract_lines_with_keywords(
                    message.clean_text,
                    ["分发", "网易内部平台", "快手", "小红书", "视频号", "B站", "抖音", "大神", "云音乐笔记"],
                ),
                must_confirm_items=self._extract_must_confirm_items(message.clean_text),
                negotiable_items=self._extract_negotiable_items(message.clean_text),
                notes=self._extract_brief_notes(message.clean_text),
            )
            brief_cards.append(brief_card)

        return brief_cards

    def infer_conversation_traits(self, messages: list[ConversationMessage]) -> list[CreatorTraitEvidence]:
        creator_messages = [message for message in messages if message.role == "creator"]
        creator_text = "\n".join(message.clean_text for message in creator_messages)

        traits: list[CreatorTraitEvidence] = [
            self._infer_order_saturation(creator_messages, creator_text),
            self._infer_flexibility_level(creator_messages, creator_text),
            self._infer_interaction_style(creator_messages, creator_text),
            self._infer_decision_speed(creator_messages, creator_text),
        ]
        return traits

    def segment_episodes(
        self,
        messages: list[ConversationMessage],
        conversation_traits: list[CreatorTraitEvidence],
    ) -> list[NegotiationEpisode]:
        annotated_messages = [
            {"message": message, "anchor_stage": self._infer_message_stage(message)}
            for message in messages
        ]
        raw_episodes: list[list[dict]] = []
        current: list[dict] = []
        current_stage = ""

        for annotated in annotated_messages:
            stage = annotated["anchor_stage"]
            if not current:
                current = [annotated]
                current_stage = stage
                continue

            if self._should_start_new_episode(current, current_stage, stage):
                raw_episodes.append(current)
                current = [annotated]
                current_stage = stage
                continue

            current.append(annotated)
            if not current_stage and stage:
                current_stage = stage

        if current:
            raw_episodes.append(current)

        raw_episodes = self._merge_small_episodes(raw_episodes)

        episodes: list[NegotiationEpisode] = []
        for idx, raw_episode in enumerate(raw_episodes, start=1):
            episode_messages = [item["message"] for item in raw_episode]
            workflow_stage = self._infer_episode_stage(raw_episode)
            episode_goal = self._map_goal(workflow_stage)
            objection_type = self._infer_objection_type(episode_messages)
            creator_response_type = self._infer_creator_response_type(episode_messages, workflow_stage)
            outcome = self._infer_outcome(episode_messages, workflow_stage, creator_response_type)
            listed_price, target_price = self._extract_episode_prices(episode_messages)
            current_rebate_rate, target_rebate_rate = self._extract_episode_rebate_rates(episode_messages)
            rebate_target_status = self._infer_rebate_target_status(current_rebate_rate, target_rebate_rate)
            rights_gap_status = self._infer_rights_gap_status(episode_messages, objection_type)
            payment_blocker_type = self._infer_payment_blocker_type(episode_messages)
            agency_margin_pressure = self._infer_agency_margin_pressure(episode_messages)
            summary = self._build_episode_summary(episode_messages, workflow_stage, objection_type)
            confidence = self._compute_episode_confidence(workflow_stage, objection_type, episode_messages)
            knowledge_base = self._map_knowledge_base(workflow_stage)

            episode = NegotiationEpisode(
                episode_id=f"episode_{short_hash(episode_messages[0].message_id + str(idx))}",
                conversation_id=episode_messages[0].conversation_id,
                creator_id=episode_messages[0].creator_id,
                knowledge_base=knowledge_base,
                workflow_stage=workflow_stage,
                episode_goal=episode_goal,
                objection_type=objection_type,
                agency_strategy=self._infer_agency_strategies(episode_messages),
                creator_response_type=creator_response_type,
                outcome=outcome,
                evidence_message_ids=[message.message_id for message in episode_messages],
                message_ids=[message.message_id for message in episode_messages],
                source_refs=[ref for message in episode_messages for ref in message.source_refs],
                creator_traits=conversation_traits,
                listed_price=listed_price,
                target_price=target_price,
                current_rebate_rate=current_rebate_rate,
                target_rebate_rate=target_rebate_rate,
                rebate_target_status=rebate_target_status,
                agency_margin_pressure=agency_margin_pressure,
                rights_gap_status=rights_gap_status,
                payment_blocker_type=payment_blocker_type,
                summary=summary,
                confidence=confidence,
                needs_review=workflow_stage == "contact_established" or confidence < 0.7,
            )
            episodes.append(episode)

        return episodes

    def build_playbook_steps(self) -> list[WorkflowPlaybookStep]:
        return [
            WorkflowPlaybookStep(
                step_id=item["step_id"],
                knowledge_base=item["knowledge_base"],
                workflow_stage=item["workflow_stage"],
                trigger_condition=item["trigger_condition"],
                required_inputs=item["required_inputs"],
                recommended_action=item["recommended_action"],
                fallback_action=item["fallback_action"],
                exit_condition=item["exit_condition"],
            )
            for item in MANUAL_PLAYBOOK_STEPS
        ]

    def mine_talk_templates(
        self,
        episodes: list[NegotiationEpisode],
        messages: list[ConversationMessage],
    ) -> list[TalkTemplate]:
        message_map = {message.message_id: message for message in messages}
        grouped: dict[tuple[str, str], TalkTemplate] = {}

        for episode in episodes:
            scenario_key = self._build_scenario_key(episode.workflow_stage, episode.episode_goal, episode.objection_type)
            for message_id in episode.message_ids:
                message = message_map[message_id]
                if message.role != "agency":
                    continue
                if not self._is_template_candidate(message.clean_text, episode.workflow_stage):
                    continue

                template_text, slots = self._parameterize_text(message.clean_text)
                key = (scenario_key, template_text)
                if key not in grouped:
                    grouped[key] = TalkTemplate(
                        template_id=f"template_{short_hash(scenario_key + template_text)}",
                        knowledge_base="talk_library",
                        scenario_key=scenario_key,
                        workflow_stage=episode.workflow_stage,
                        template_text=template_text,
                        slots=slots,
                        applicable_conditions=self._build_template_conditions(episode),
                        risk_notes=self._build_template_risk_notes(message.clean_text, episode),
                        source_episode_ids=[episode.episode_id],
                        source_message_ids=[message.message_id],
                    )
                else:
                    grouped[key].source_episode_ids = dedupe_keep_order(
                        grouped[key].source_episode_ids + [episode.episode_id]
                    )
                    grouped[key].source_message_ids = dedupe_keep_order(
                        grouped[key].source_message_ids + [message.message_id]
                    )

        for item in MANUAL_TALK_TEMPLATES:
            grouped[(item["scenario_key"], item["template_text"])] = TalkTemplate(
                template_id=item["template_id"],
                knowledge_base=item["knowledge_base"],
                scenario_key=item["scenario_key"],
                workflow_stage=item["workflow_stage"],
                template_text=item["template_text"],
                slots=item["slots"],
                applicable_conditions=item["applicable_conditions"],
                risk_notes=item["risk_notes"],
                source_episode_ids=item["source_episode_ids"],
                source_message_ids=item["source_message_ids"],
                origin=item["origin"],
            )

        templates = list(grouped.values())
        templates.sort(key=lambda template: (template.workflow_stage, template.scenario_key, template.template_id))
        return templates

    def build_retrieval_chunks(
        self,
        messages: list[ConversationMessage],
        episodes: list[NegotiationEpisode],
        talk_templates: list[TalkTemplate],
        playbook_steps: list[WorkflowPlaybookStep],
    ) -> list[RetrievalChunk]:
        chunks: list[RetrievalChunk] = []
        message_map = {message.message_id: message for message in messages}
        episode_by_message_id = {
            message_id: episode
            for episode in episodes
            for message_id in episode.message_ids
        }

        grouped_messages: dict[str, list[ConversationMessage]] = defaultdict(list)
        for message in messages:
            grouped_messages[message.conversation_id].append(message)

        for conversation_messages in grouped_messages.values():
            conversation_messages.sort(key=lambda message: message.seq_num)
            for idx, message in enumerate(conversation_messages):
                if message.role != "creator":
                    continue
                next_reply = self._find_next_agency_reply(conversation_messages, idx)
                if next_reply is None:
                    continue

                episode = episode_by_message_id.get(message.message_id) or episode_by_message_id.get(next_reply.message_id)
                if episode is None:
                    continue

                context_messages = conversation_messages[max(0, idx - 3):idx]
                bucket = self._map_sft_bucket(episode.workflow_stage)
                scenario_key = self._build_scenario_key(episode.workflow_stage, episode.episode_goal, episode.objection_type)
                filter_tags = self._build_episode_filter_tags(episode)
                filter_tags.append(f"sft_bucket:{bucket}")

                embedding_text = "\n".join(
                    [
                        f"workflow_stage: {episode.workflow_stage}",
                        f"episode_goal: {episode.episode_goal}",
                        f"objection_type: {episode.objection_type}",
                        f"context: {' | '.join(item.clean_text for item in context_messages)}",
                        f"creator_message: {message.clean_text}",
                        f"agency_reply: {next_reply.clean_text}",
                    ]
                )

                source_refs = [ref for item in context_messages + [message, next_reply] for ref in item.source_refs]
                chunks.append(
                    RetrievalChunk(
                        chunk_id=f"chunk_{short_hash(message.message_id + next_reply.message_id)}",
                        chunk_type="turn_chunk",
                        workflow_stage=episode.workflow_stage,
                        scenario_key=scenario_key,
                        knowledge_base=episode.knowledge_base,
                        embedding_text=embedding_text,
                        filter_tags=dedupe_keep_order(filter_tags),
                        source_refs=source_refs,
                        confidence=episode.confidence,
                        metadata={
                            "conversation_id": message.conversation_id,
                            "creator_id": message.creator_id,
                            "creator_message_id": message.message_id,
                            "agency_reply_id": next_reply.message_id,
                            "episode_id": episode.episode_id,
                            "sft_bucket": bucket,
                        },
                    )
                )

        for episode in episodes:
            chunks.append(
                RetrievalChunk(
                    chunk_id=f"chunk_{short_hash(episode.episode_id + 'episode')}",
                    chunk_type="episode_chunk",
                    workflow_stage=episode.workflow_stage,
                    scenario_key=self._build_scenario_key(episode.workflow_stage, episode.episode_goal, episode.objection_type),
                    knowledge_base=episode.knowledge_base,
                    embedding_text=self._build_episode_chunk_text(episode, message_map),
                    filter_tags=self._build_episode_filter_tags(episode),
                    source_refs=episode.source_refs,
                    confidence=episode.confidence,
                    metadata={
                        "episode_id": episode.episode_id,
                        "conversation_id": episode.conversation_id,
                        "creator_id": episode.creator_id,
                        "sft_bucket": self._map_sft_bucket(episode.workflow_stage),
                    },
                )
            )

        for template in talk_templates:
            chunks.append(
                RetrievalChunk(
                    chunk_id=f"chunk_{short_hash(template.template_id + 'template')}",
                    chunk_type="template_chunk",
                    workflow_stage=template.workflow_stage,
                    scenario_key=template.scenario_key,
                    knowledge_base=template.knowledge_base,
                    embedding_text="\n".join(
                        [
                            f"workflow_stage: {template.workflow_stage}",
                            f"scenario_key: {template.scenario_key}",
                            f"template_text: {template.template_text}",
                            f"conditions: {' | '.join(template.applicable_conditions)}",
                            f"risk_notes: {' | '.join(template.risk_notes)}",
                        ]
                    ),
                    filter_tags=dedupe_keep_order(
                        [f"workflow_stage:{template.workflow_stage}", f"scenario_key:{template.scenario_key}", f"knowledge_base:{template.knowledge_base}"]
                        + [f"slot:{slot}" for slot in template.slots]
                    ),
                    source_refs=[{"origin": template.origin, "source_episode_ids": template.source_episode_ids, "source_message_ids": template.source_message_ids}],
                    confidence=0.95 if template.origin == "manual_seed" else 0.8,
                    metadata={"template_id": template.template_id, "origin": template.origin},
                )
            )

        for step in playbook_steps:
            chunks.append(
                RetrievalChunk(
                    chunk_id=f"chunk_{short_hash(step.step_id + 'policy')}",
                    chunk_type="policy_chunk",
                    workflow_stage=step.workflow_stage,
                    scenario_key=f"{step.workflow_stage}.policy.default",
                    knowledge_base=step.knowledge_base,
                    embedding_text="\n".join(
                        [
                            f"workflow_stage: {step.workflow_stage}",
                            f"trigger_condition: {step.trigger_condition}",
                            f"required_inputs: {' | '.join(step.required_inputs)}",
                            f"recommended_action: {step.recommended_action}",
                            f"fallback_action: {step.fallback_action}",
                            f"exit_condition: {step.exit_condition}",
                        ]
                    ),
                    filter_tags=[
                        f"workflow_stage:{step.workflow_stage}",
                        f"knowledge_base:{step.knowledge_base}",
                        "policy_card",
                    ],
                    source_refs=[{"origin": "manual_seed", "step_id": step.step_id}],
                    confidence=0.98,
                    metadata={"step_id": step.step_id},
                )
            )

        return chunks

    def _looks_like_brief_delivery(self, text: str) -> bool:
        header_hits = sum(marker in text for marker in BRIEF_MARKERS)
        return header_hits >= 2 or ("合作需求" in text and "报价" in text)

    def _extract_brand(self, text: str) -> str | None:
        for label in ["品牌", "项目", "【逆水寒】"]:
            value = self._extract_labeled_value(text, label)
            if value:
                return value
        if "逆水寒" in text:
            return "网易逆水寒"
        return None

    def _extract_product(self, text: str) -> str | None:
        for label in ["产品", "游戏", "项目"]:
            value = self._extract_labeled_value(text, label)
            if value:
                return value
        if "逆水寒" in text:
            return "逆水寒"
        return None

    def _extract_platform_value(self, text: str) -> str:
        platforms = []
        if "B站" in text:
            platforms.append("bilibili")
        if "抖音" in text:
            platforms.append("douyin")
        if "小红书" in text:
            platforms.append("xiaohongshu")
        if "快手" in text:
            platforms.append("kuaishou")
        return ",".join(platforms) if platforms else PLATFORM

    def _extract_deliverable_type(self, text: str) -> str | None:
        parts = []
        if "B站" in text and "定制视频" in text:
            parts.append("B站定制视频")
        if "60s+" in text:
            parts.append("60s+视频")
        if "21-60s" in text:
            parts.append("21-60s视频")
        if "1-20s" in text:
            parts.append("1-20s视频")
        if "水下" in text:
            parts.append("水下合作")
        if "口播" in text:
            parts.append("口播")
        return " / ".join(dedupe_keep_order(parts)) or None

    def _extract_content_direction(self, text: str) -> str | None:
        for label in ["合作需求", "需求", "【合作需求】"]:
            block = self._extract_block_after_label(text, label)
            if block:
                return block
        return None

    def _extract_schedule_window(self, text: str) -> str | None:
        for label in ["合作档期", "【合作档期】", "档期"]:
            block = self._extract_block_after_label(text, label)
            if block:
                return block
        return None

    def _extract_lines_with_keywords(self, text: str, keywords: list[str]) -> list[str]:
        lines = []
        for line in text.splitlines():
            if any(keyword in line for keyword in keywords):
                lines.append(line.strip())
        return dedupe_keep_order(lines)

    def _extract_must_confirm_items(self, text: str) -> list[str]:
        items = [line.strip() for line in text.splitlines() if NUMBERED_ITEM_PATTERN.match(line.strip())]
        return dedupe_keep_order(items)

    def _extract_negotiable_items(self, text: str) -> list[str]:
        candidates = []
        for line in text.splitlines():
            if any(keyword in line for keyword in ["优先", "如不可", "如果不能", "可否", "希望", "如无"]):
                candidates.append(line.strip())
        return dedupe_keep_order(candidates)

    def _extract_brief_notes(self, text: str) -> list[str]:
        notes = []
        if "参考视频" in text or "参考链接" in text:
            notes.append("包含参考内容链接")
        if "永久保留" in text:
            notes.append("包含永久保留要求")
        if "48h" in text or "3天" in text:
            notes.append("包含发布后不更新约束")
        return notes

    def _extract_labeled_value(self, text: str, label: str) -> str | None:
        pattern = re.compile(rf"{re.escape(label)}[：:]\s*([^\n]+)")
        match = pattern.search(text)
        if match:
            return match.group(1).strip()
        if label.startswith("【") and label.endswith("】") and label in text:
            return label.strip("【】")
        return None

    def _extract_block_after_label(self, text: str, label: str) -> str | None:
        lines = text.splitlines()
        for idx, line in enumerate(lines):
            if label not in line:
                continue
            direct_value = self._extract_labeled_value(line, label)
            if direct_value:
                return direct_value

            block_lines = []
            for next_line in lines[idx + 1:]:
                stripped = next_line.strip()
                if not stripped:
                    if block_lines:
                        break
                    continue
                if stripped.startswith("【") and block_lines:
                    break
                if stripped.endswith("：") and block_lines:
                    break
                block_lines.append(stripped)
            if block_lines:
                return " ".join(block_lines)
        return None

    def _infer_order_saturation(self, messages: list[ConversationMessage], creator_text: str) -> CreatorTraitEvidence:
        high_keywords = ["同步问的人也很多", "好几个同步和您预约同一个档期", "不一定能给您留住", "只有付款之后才能给您留档期"]
        medium_keywords = ["最快", "来不及", "档期", "我主要是b站独家"]
        low_keywords = ["少赚点了", "也行", "下次多合作"]

        if self._count_hits(creator_text, high_keywords) > 0:
            return CreatorTraitEvidence(
                trait_name="order_saturation",
                value="high",
                confidence=0.9,
                evidence_message_ids=self._find_message_ids_with_keywords(messages, high_keywords),
                rationale="达人明确提到多人竞争同一档期或只接受付款后留档。",
            )
        if self._count_hits(creator_text, low_keywords) > 0:
            return CreatorTraitEvidence(
                trait_name="order_saturation",
                value="low",
                confidence=0.72,
                evidence_message_ids=self._find_message_ids_with_keywords(messages, low_keywords),
                rationale="达人愿意主动让利，缺单概率相对更高。",
            )
        if self._count_hits(creator_text, medium_keywords) > 0:
            return CreatorTraitEvidence(
                trait_name="order_saturation",
                value="medium",
                confidence=0.62,
                evidence_message_ids=self._find_message_ids_with_keywords(messages, medium_keywords),
                rationale="达人表现出档期有限，但未明确说明排满。",
            )
        return CreatorTraitEvidence(
            trait_name="order_saturation",
            value="unknown",
            confidence=0.35,
            evidence_message_ids=[],
            rationale="暂无足够证据判断是否缺单。",
        )

    def _infer_flexibility_level(self, messages: list[ConversationMessage], creator_text: str) -> CreatorTraitEvidence:
        high_keywords = ["25也行", "少赚点了", "可以承担200", "可以的", "没问题"]
        rigid_keywords = ["不能高了", "改不了", "必须要下单", "公司统一", "不接受", "只接受", "不保量", "不行"]
        negotiable_keywords = ["我看看", "我跟公司反映一下", "可以沟通", "稍等一下"]

        if self._count_hits(creator_text, rigid_keywords) >= 2:
            return CreatorTraitEvidence(
                trait_name="flexibility_level",
                value="rigid",
                confidence=0.86,
                evidence_message_ids=self._find_message_ids_with_keywords(messages, rigid_keywords),
                rationale="达人多次强调固定规则或拒绝变通。",
            )
        if self._count_hits(creator_text, high_keywords) >= 2:
            return CreatorTraitEvidence(
                trait_name="flexibility_level",
                value="highly_flexible",
                confidence=0.78,
                evidence_message_ids=self._find_message_ids_with_keywords(messages, high_keywords),
                rationale="达人明确接受让利或共同承担成本。",
            )
        if self._count_hits(creator_text, negotiable_keywords) > 0:
            return CreatorTraitEvidence(
                trait_name="flexibility_level",
                value="negotiable",
                confidence=0.68,
                evidence_message_ids=self._find_message_ids_with_keywords(messages, negotiable_keywords),
                rationale="达人愿意再沟通，但未承诺一定放宽规则。",
            )
        return CreatorTraitEvidence(
            trait_name="flexibility_level",
            value="unknown",
            confidence=0.35,
            evidence_message_ids=[],
            rationale="缺乏足够让利或拒绝证据。",
        )

    def _infer_interaction_style(self, messages: list[ConversationMessage], creator_text: str) -> CreatorTraitEvidence:
        friendly_score = self._count_hits(creator_text, ["宝", "哈", "～", "好的", "收到", "好嘞", "[动画表情]"])
        professional_score = self._count_hits(creator_text, ["营业执照", "开户地址", "开票", "报价", "合作须知", "公司"])
        strong_boundary_score = self._count_hits(creator_text, ["不能", "不接受", "改不了", "必须", "统一"])
        cautious_score = self._count_hits(creator_text, ["稍等", "我看看", "我问问", "申请一下"])

        if strong_boundary_score >= 3:
            value = "strong_boundary"
            rationale = "达人反复强调边界、规则和不可变通项。"
            evidence_ids = self._find_message_ids_with_keywords(messages, ["不能", "不接受", "改不了", "必须", "统一"])
            confidence = 0.82
        elif professional_score >= friendly_score and professional_score >= cautious_score and professional_score > 1:
            value = "professional"
            rationale = "达人提供完整报价、对公信息或规则说明，整体更流程化。"
            evidence_ids = self._find_message_ids_with_keywords(messages, ["报价", "合作须知", "营业执照", "公司"])
            confidence = 0.74
        elif cautious_score >= 3:
            value = "cautious"
            rationale = "达人多次出现“稍等”“我看看”类回复，推进偏谨慎。"
            evidence_ids = self._find_message_ids_with_keywords(messages, ["稍等", "我看看", "我问问"])
            confidence = 0.69
        elif friendly_score >= 2:
            value = "friendly"
            rationale = "达人整体回复亲和，常用口语和缓和词。"
            evidence_ids = self._find_message_ids_with_keywords(messages, ["宝", "哈", "好的", "收到"])
            confidence = 0.72
        else:
            value = "direct"
            rationale = "达人回复较直接、较短，信息导向明显。"
            evidence_ids = [message.message_id for message in messages[:2]]
            confidence = 0.58

        return CreatorTraitEvidence(
            trait_name="interaction_style",
            value=value,
            confidence=confidence,
            evidence_message_ids=evidence_ids,
            rationale=rationale,
        )

    def _infer_decision_speed(self, messages: list[ConversationMessage], creator_text: str) -> CreatorTraitEvidence:
        slow_keywords = ["稍等", "我看看", "我问问", "申请一下", "晚一点"]
        fast_keywords = ["可以", "确认", "来了", "没问题", "马上", "收到"]

        slow_hits = self._count_hits(creator_text, slow_keywords)
        fast_hits = self._count_hits(creator_text, fast_keywords)

        if slow_hits >= 4 and slow_hits > fast_hits:
            return CreatorTraitEvidence(
                trait_name="decision_speed",
                value="slow",
                confidence=0.71,
                evidence_message_ids=self._find_message_ids_with_keywords(messages, slow_keywords),
                rationale="达人多次需要等待内部确认或自行判断。",
            )
        if fast_hits >= 6 and fast_hits > slow_hits:
            return CreatorTraitEvidence(
                trait_name="decision_speed",
                value="fast",
                confidence=0.73,
                evidence_message_ids=self._find_message_ids_with_keywords(messages, fast_keywords),
                rationale="达人快速确认档期、报价或配合事项。",
            )
        return CreatorTraitEvidence(
            trait_name="decision_speed",
            value="normal",
            confidence=0.55,
            evidence_message_ids=self._find_message_ids_with_keywords(messages, ["可以", "稍等", "我看看"], limit=4),
            rationale="回复节奏整体处于常规水平。",
        )

    def _count_hits(self, text: str, keywords: Iterable[str]) -> int:
        return sum(keyword in text for keyword in keywords)

    def _find_message_ids_with_keywords(
        self,
        messages: list[ConversationMessage],
        keywords: Iterable[str],
        limit: int = 4,
    ) -> list[str]:
        ids: list[str] = []
        for message in messages:
            if any(keyword in message.clean_text for keyword in keywords):
                ids.append(message.message_id)
            if len(ids) >= limit:
                break
        return ids

    def _infer_message_stage(self, message: ConversationMessage) -> str:
        text = message.clean_text
        role = message.role

        scores: dict[str, int] = defaultdict(int)

        if any(marker in text for marker in CONTACT_MARKERS):
            scores["contact_established"] += 12
        if role == "agency" and any(marker in text for marker in COLD_OUTREACH_MARKERS) and len(text) <= 80:
            scores["cold_outreach"] += 6
        if role == "agency" and self._looks_like_brief_delivery(text):
            scores["brief_delivery"] += 11
        if role == "creator" and self._looks_like_quote_response(text):
            scores["quote_collection"] += 11
        if self._count_hits(text, REBATE_MARKERS) > 0:
            scores["rebate_negotiation"] += 9
        if self._count_hits(text, PRICE_NEGOTIATION_MARKERS) > 0:
            scores["price_negotiation"] += 8
        if self._count_hits(text, RIGHTS_MARKERS) > 0 and self._count_hits(text, LIMIT_MARKERS) > 0:
            scores["rights_negotiation"] += 8
        if self._count_hits(text, DOC_MARKERS) >= 2:
            scores["supplier_onboarding"] += 10
        if self._count_hits(text, PAYMENT_MARKERS) > 0:
            scores["payment_push"] += 8
        if self._count_hits(text, EXECUTION_MARKERS) > 0:
            scores["execution_followup"] += 7
        if self._count_hits(text, REVISION_MARKERS) > 1:
            scores["revision_coordination"] += 8
        if self._count_hits(text, DATA_MARKERS) > 1:
            scores["data_feedback"] += 9
        if self._count_hits(text, REBATE_RECOVERY_MARKERS) > 0:
            scores["rebate_recovery"] += 10
        if self._count_hits(text, REPEAT_MARKERS) > 0:
            scores["repeat_collaboration"] += 7
        if self._count_hits(text, CONFIRM_MARKERS) > 0:
            scores["cooperation_confirmation"] += 8
        if self._count_hits(text, SCHEDULE_MARKERS) > 0:
            scores["schedule_lock"] += 6
        if "发布" in text and any(marker in text for marker in ["48h", "3天", "上线", "发稿", "保留"]):
            scores["publication_confirmation"] += 7

        if not scores:
            return ""
        stage, _ = max(scores.items(), key=lambda item: (item[1], self._stage_priority(item[0])))
        return stage

    def _looks_like_quote_response(self, text: str) -> bool:
        numbered_lines = len([line for line in text.splitlines() if NUMBERED_ITEM_PATTERN.match(line.strip())])
        quote_hits = self._count_hits(text, QUOTE_MARKERS + RIGHTS_MARKERS)
        return numbered_lines >= 4 and quote_hits >= 4

    def _stage_priority(self, stage: str) -> int:
        order = list(WORKFLOW_STAGES.keys())
        if stage not in order:
            return -1
        return len(order) - order.index(stage)

    def _should_start_new_episode(
        self,
        current: list[dict],
        current_stage: str,
        new_stage: str,
    ) -> bool:
        if not new_stage:
            return False
        if not current_stage:
            return len(current) >= 3
        if new_stage == current_stage:
            return False
        if current_stage in {"cold_outreach", "contact_established"}:
            return True
        if new_stage in {
            "brief_delivery",
            "quote_collection",
            "rights_negotiation",
            "price_negotiation",
            "rebate_negotiation",
            "schedule_lock",
            "cooperation_confirmation",
            "supplier_onboarding",
            "payment_push",
            "execution_followup",
            "revision_coordination",
            "publication_confirmation",
            "data_feedback",
            "rebate_recovery",
        } and len(current) >= 2:
            return True
        return False

    def _merge_small_episodes(self, episodes: list[list[dict]]) -> list[list[dict]]:
        merged: list[list[dict]] = []
        for raw_episode in episodes:
            if not merged:
                merged.append(raw_episode)
                continue
            stage = self._infer_episode_stage(raw_episode)
            previous_stage = self._infer_episode_stage(merged[-1])
            if len(raw_episode) <= 2 and (not stage or stage == previous_stage or stage == "contact_established"):
                merged[-1].extend(raw_episode)
            else:
                merged.append(raw_episode)
        return merged

    def _infer_episode_stage(self, raw_episode: list[dict]) -> str:
        counts: Counter[str] = Counter(item["anchor_stage"] for item in raw_episode if item["anchor_stage"])
        if counts:
            return counts.most_common(1)[0][0]
        combined_text = "\n".join(item["message"].clean_text for item in raw_episode)
        synthetic_message = raw_episode[0]["message"]
        fallback = ConversationMessage(
            message_id=synthetic_message.message_id,
            conversation_id=synthetic_message.conversation_id,
            platform=synthetic_message.platform,
            channel_type=synthetic_message.channel_type,
            creator_id=synthetic_message.creator_id,
            creator_aliases=synthetic_message.creator_aliases,
            media_id=synthetic_message.media_id,
            media_name=synthetic_message.media_name,
            role="agency",
            raw_text=combined_text,
            clean_text=combined_text,
            timestamp=synthetic_message.timestamp,
            formatted_time=synthetic_message.formatted_time,
        )
        return self._infer_message_stage(fallback) or "contact_established"

    def _map_goal(self, workflow_stage: str) -> str:
        mapping = {
            "cold_outreach": "get_reply",
            "contact_established": "get_reply",
            "brief_delivery": "collect_quote",
            "quote_collection": "collect_quote",
            "rights_negotiation": "confirm_rights",
            "price_negotiation": "cut_price",
            "rebate_negotiation": "raise_rebate",
            "schedule_lock": "secure_schedule",
            "cooperation_confirmation": "lock_execution",
            "supplier_onboarding": "collect_docs",
            "payment_push": "push_payment",
            "execution_followup": "lock_execution",
            "revision_coordination": "lock_execution",
            "publication_confirmation": "confirm_publish",
            "data_feedback": "collect_data",
            "rebate_recovery": "recover_rebate",
            "repeat_collaboration": "lock_execution",
        }
        return mapping.get(workflow_stage, "collect_quote")

    def _infer_objection_type(self, messages: list[ConversationMessage]) -> str:
        combined_text = "\n".join(message.clean_text for message in messages)
        if "返点" in combined_text and any(keyword in combined_text for keyword in ["最高能给到", "返点25", "返点30", "服务费", "利润", "反给"]):
            return "rebate_below_target"
        if any(keyword in combined_text for keyword in ["报价贵", "核价", "便宜", "优惠", "改价", "刊例价", "客户说"]):
            return "price_too_high"
        if any(keyword in combined_text for keyword in ["必须要下单", "付款之后", "请款有固定时间", "尾款", "充值", "财务"]):
            return "payment_rule_rigid"
        if any(keyword in combined_text for keyword in ["档期", "留档", "锁档", "定金", "有风险", "来不及"]):
            return "schedule_risk"
        if any(keyword in combined_text for keyword in ["营业执照", "入库", "开户地址", "开户行", "账号", "身份证"]) and any(
            keyword in combined_text for keyword in ["稍后", "缺", "等待", "申请", "催催"]
        ):
            return "document_missing"
        if any(keyword in combined_text for keyword in ["免费分发", "赠送"]) and any(keyword in combined_text for keyword in ["收费", "不免费", "任选一个", "不能"]):
            return "no_free_distribution"
        if "二创" in combined_text and any(keyword in combined_text for keyword in ["不接受", "不可以", "不能"]):
            return "no_secondary_creation"
        if any(keyword in combined_text for keyword in ["授权", "投流", "保留", "不更新"]) and any(keyword in combined_text for keyword in ["只授权", "不接受", "不可以", "只能"]):
            return "rights_limited"
        if any(keyword in combined_text for keyword in ["不保量", "不保证", "w赞", "播放量"]) and any(keyword in combined_text for keyword in ["不保", "无法", "看跑"]):
            return "cannot_guarantee_metrics"
        if any(keyword in combined_text for keyword in ["公司统一", "平台", "花火", "星图", "规定"]) and any(keyword in combined_text for keyword in ["不能", "改不了", "罚"]):
            return "platform_rule_rigid"
        return "none"

    def _infer_agency_strategies(self, messages: list[ConversationMessage]) -> list[str]:
        agency_text = "\n".join(message.clean_text for message in messages if message.role == "agency")
        strategies: list[str] = []
        if any(keyword in agency_text for keyword in ["求求", "辛苦", "麻烦", "感谢", "宝子"]):
            strategies.append("soft_push")
        if any(keyword in agency_text for keyword in ["0服务费", "利润", "借了", "借钱", "利润不够"]):
            strategies.append("margin_pressure_disclosure")
        if any(keyword in agency_text for keyword in ["能不能", "跟你们那边沟通下", "再高些么", "最高能给到多少"]):
            strategies.append("ask_exception")
        if any(keyword in agency_text for keyword in ["或者", "换", "送", "赠送", "延更", "选一个"]):
            strategies.append("offer_tradeoff")
        if any(keyword in agency_text for keyword in ["今天", "明天", "节前", "档期", "赶一赶", "30号"]):
            strategies.append("deadline_pressure")
        if any(keyword in agency_text for keyword in ["流程", "入库", "公司", "请款", "财务", "执行"]):
            strategies.append("process_explanation")
        if not strategies:
            strategies.append("standard_information_exchange")
        return dedupe_keep_order(strategies)

    def _infer_creator_response_type(self, messages: list[ConversationMessage], workflow_stage: str) -> str:
        creator_text = "\n".join(message.clean_text for message in messages if message.role == "creator")
        if workflow_stage == "quote_collection" and creator_text:
            return "provided_quote"
        if workflow_stage == "supplier_onboarding" and creator_text:
            return "provided_docs"
        if workflow_stage == "schedule_lock" and any(keyword in creator_text for keyword in ["可以", "在", "没问题", "档期", "最快"]):
            return "confirmed_schedule"
        if any(keyword in creator_text for keyword in ["稍等", "我看看", "我问问", "申请一下"]):
            return "pending_internal_sync"
        if any(keyword in creator_text for keyword in ["不能", "不接受", "改不了", "不可以", "不行"]):
            if any(keyword in creator_text for keyword in ["公司", "规定", "统一", "平台"]):
                return "rule_bound_refusal"
            return "refused"
        if any(keyword in creator_text for keyword in ["但是", "不过", "只能", "可以", "行"]):
            return "partial_acceptance"
        if any(keyword in creator_text for keyword in ["可以", "确认", "好的", "没问题"]):
            return "accepted"
        if any(keyword in creator_text for keyword in ["什么情况", "哪个产品", "是哪个", "什么平台"]):
            return "requested_more_info"
        return "information_exchange"

    def _infer_outcome(self, messages: list[ConversationMessage], workflow_stage: str, creator_response_type: str) -> str:
        combined_text = "\n".join(message.clean_text for message in messages)
        if workflow_stage in {"cooperation_confirmation", "execution_followup"} and any(keyword in combined_text for keyword in ["确认合作", "拉群", "开始制作", "推进"]):
            return "confirmed"
        if creator_response_type in {"accepted", "provided_quote", "provided_docs", "confirmed_schedule"}:
            return "advanced"
        if creator_response_type == "partial_acceptance":
            return "partial_progress"
        if creator_response_type in {"pending_internal_sync", "requested_more_info"}:
            return "waiting"
        if creator_response_type in {"refused", "rule_bound_refusal"}:
            return "blocked"
        return "advanced" if workflow_stage in {"brief_delivery", "quote_collection"} else "waiting"

    def _extract_episode_prices(self, messages: list[ConversationMessage]) -> tuple[float | None, float | None]:
        creator_text = "\n".join(message.clean_text for message in messages if message.role == "creator")
        agency_text = "\n".join(message.clean_text for message in messages if message.role == "agency")
        listed_price = self._extract_first_amount(creator_text, ["报价", "一口价", "价格", "私单", "星图", "水下"])
        target_price = self._extract_first_amount(agency_text, ["改价", "下单", "报价", "刊例价", "这样嘛"])
        return listed_price, target_price

    def _extract_first_amount(self, text: str, contexts: list[str]) -> float | None:
        if not text:
            return None
        for line in text.splitlines():
            if not any(context in line for context in contexts):
                continue
            token = self._extract_amount_token(line)
            if token is not None:
                return token
        for line in text.splitlines():
            token = self._extract_amount_token(line)
            if token is not None:
                return token
        return None

    def _extract_amount_token(self, text: str) -> float | None:
        for match in AMOUNT_TOKEN_PATTERN.finditer(text):
            token = match.group(0).strip()
            if not token or token in {"0", "1", "2", "3"}:
                continue
            normalized = self._normalize_amount(token)
            if normalized is None:
                continue
            if normalized < 5 and "w" not in token.lower() and "万" not in token:
                continue
            return normalized
        return None

    def _normalize_amount(self, token: str) -> float | None:
        normalized = token.replace("¥", "").replace("￥", "").replace(",", "").strip()
        multiplier = 1.0
        if normalized.lower().endswith("w") or normalized.endswith("万"):
            normalized = normalized[:-1]
            multiplier = 10000.0
        try:
            return float(normalized) * multiplier
        except ValueError:
            return None

    def _extract_episode_rebate_rates(self, messages: list[ConversationMessage]) -> tuple[float | None, float | None]:
        creator_text = "\n".join(message.clean_text for message in messages if message.role == "creator")
        agency_text = "\n".join(message.clean_text for message in messages if message.role == "agency")
        current_rate = self._extract_rebate_rate(creator_text)
        target_rate = self._extract_rebate_rate(agency_text)
        return current_rate, target_rate

    def _extract_rebate_rate(self, text: str) -> float | None:
        if "返点" not in text and "返" not in text:
            return None
        for match in PERCENT_PATTERN.finditer(text):
            value = float(match.group(1))
            if 0 < value <= 60:
                return round(value / 100.0, 4)
        simple_match = re.search(r"返点(?:最高能给到|能给到|是)?[：: ]*([0-9]{1,2}(?:\.\d+)?)", text)
        if simple_match:
            value = float(simple_match.group(1))
            if 0 < value <= 60:
                return round(value / 100.0, 4)
        return None

    def _infer_rebate_target_status(
        self,
        current_rate: float | None,
        target_rate: float | None,
    ) -> str:
        if current_rate is None and target_rate is None:
            return "unknown"
        if target_rate is None:
            return "not_requested"
        if current_rate is None:
            return "unknown"
        return "met" if current_rate >= target_rate else "below_target"

    def _infer_rights_gap_status(self, messages: list[ConversationMessage], objection_type: str) -> str:
        combined_text = "\n".join(message.clean_text for message in messages)
        if objection_type in {"rights_limited", "no_free_distribution", "no_secondary_creation"}:
            return "limited"
        if any(keyword in combined_text for keyword in ["可以", "可", "免费"]) and any(keyword in combined_text for keyword in RIGHTS_MARKERS):
            return "aligned"
        if any(keyword in combined_text for keyword in RIGHTS_MARKERS):
            return "open"
        return "unknown"

    def _infer_payment_blocker_type(self, messages: list[ConversationMessage]) -> str:
        agency_text = "\n".join(message.clean_text for message in messages if message.role == "agency")
        creator_text = "\n".join(message.clean_text for message in messages if message.role == "creator")
        combined_text = agency_text + "\n" + creator_text

        if any(keyword in agency_text for keyword in ["请款", "财务", "固定时间", "充值", "审核"]):
            return "internal_approval"
        if any(keyword in creator_text for keyword in ["必须要下单", "付款之后", "公司有规定", "定金"]):
            return "supplier_rule"
        if any(keyword in combined_text for keyword in ["营业执照", "入库"]) and any(keyword in combined_text for keyword in ["稍后", "还在", "申请", "催"]):
            return "document_missing"
        if any(keyword in combined_text for keyword in ["平台", "花火", "星图"]) and any(keyword in combined_text for keyword in ["规定", "罚", "审核不过"]):
            return "platform_rule"
        return "none"

    def _infer_agency_margin_pressure(self, messages: list[ConversationMessage]) -> str:
        agency_text = "\n".join(message.clean_text for message in messages if message.role == "agency")
        if any(keyword in agency_text for keyword in ["0服务费", "利润不够", "借了", "借钱", "扣完利润", "利润就不够"]):
            return "high"
        if any(keyword in agency_text for keyword in ["核价", "报价贵", "预算", "卡核价", "求求"]):
            return "medium"
        if "返点" in agency_text or "改价" in agency_text:
            return "medium"
        return "low"

    def _build_episode_summary(
        self,
        messages: list[ConversationMessage],
        workflow_stage: str,
        objection_type: str,
    ) -> str:
        first_meaningful = next((message.clean_text for message in messages if message.clean_text), "")
        last_meaningful = next((message.clean_text for message in reversed(messages) if message.clean_text), "")
        return f"{workflow_stage} / objection={objection_type} / start={first_meaningful[:60]} / end={last_meaningful[:60]}"

    def _compute_episode_confidence(
        self,
        workflow_stage: str,
        objection_type: str,
        messages: list[ConversationMessage],
    ) -> float:
        score = 0.55
        if workflow_stage in WORKFLOW_STAGES:
            score += 0.15
        if objection_type != "none":
            score += 0.1
        if len(messages) >= 3:
            score += 0.1
        if any(message.role == "creator" for message in messages) and any(message.role == "agency" for message in messages):
            score += 0.1
        return min(score, 0.95)

    def _map_knowledge_base(self, workflow_stage: str) -> str:
        if workflow_stage in {"brief_delivery", "quote_collection"}:
            return "brief_framework"
        if workflow_stage in {"rights_negotiation", "price_negotiation", "rebate_negotiation", "schedule_lock"}:
            return "negotiation_scene"
        if workflow_stage in {"cold_outreach", "contact_established", "repeat_collaboration"}:
            return "talk_library"
        return "fulfillment_sop"

    def _build_scenario_key(self, workflow_stage: str, episode_goal: str, objection_type: str) -> str:
        return f"{workflow_stage}.{episode_goal}.{objection_type}"

    def _is_template_candidate(self, text: str, workflow_stage: str) -> bool:
        normalized = normalize_text(text)
        if not normalized or normalized in COMMON_NOISE_MESSAGES:
            return False
        if normalized.startswith("[") and normalized.endswith("]"):
            return False
        if len(normalized) < 6:
            return False
        if any(keyword in normalized for keyword in RISKY_TEMPLATE_MARKERS):
            return False
        if workflow_stage == "contact_established":
            return False
        return True

    def _parameterize_text(self, text: str) -> tuple[str, list[str]]:
        slots: list[str] = []
        patterns = [
            (re.compile(r"https?://[^\s]+"), "[URL]", "URL"),
            (re.compile(r"\d{4}-\d{1,2}-\d{1,2}"), "[DATE]", "DATE"),
            (re.compile(r"\d{1,2}\.\d{1,2}(?:-\d{1,2}(?:\.\d{1,2})?)?"), "[DATE_OR_SLOT]", "DATE_OR_SLOT"),
            (re.compile(r"\d{1,2}月\d{1,2}日"), "[DATE]", "DATE"),
            (re.compile(r"\d{1,2}:\d{2}"), "[TIME]", "TIME"),
            (re.compile(r"([0-9]{1,2}(?:\.\d+)?)\s*[%％]"), "[PERCENT]", "PERCENT"),
            (re.compile(r"[¥￥]?\d+(?:\.\d+)?\s*(?:[wW万])"), "[AMOUNT]", "AMOUNT"),
            (re.compile(r"\b\d{4,}\b"), "[NUMBER]", "NUMBER"),
            (re.compile(r"@[^\s，。！？,.!?]+"), "[MENTION]", "MENTION"),
        ]

        template = text
        for pattern, replacement, slot_name in patterns:
            if pattern.search(template):
                template = pattern.sub(replacement, template)
                slots.append(slot_name)

        return template, dedupe_keep_order(slots)

    def _build_template_conditions(self, episode: NegotiationEpisode) -> list[str]:
        conditions = [
            f"workflow_stage={episode.workflow_stage}",
            f"episode_goal={episode.episode_goal}",
        ]
        if episode.objection_type != "none":
            conditions.append(f"objection_type={episode.objection_type}")
        if episode.rebate_target_status != "unknown":
            conditions.append(f"rebate_target_status={episode.rebate_target_status}")
        for trait in episode.creator_traits:
            if trait.value != "unknown":
                conditions.append(f"{trait.trait_name}={trait.value}")
        return dedupe_keep_order(conditions)

    def _build_template_risk_notes(self, text: str, episode: NegotiationEpisode) -> list[str]:
        notes: list[str] = []
        if any(keyword in text for keyword in ["求求", "辛苦", "麻烦"]):
            notes.append("适合软推动场景，避免连续高频使用。")
        if episode.objection_type == "payment_rule_rigid":
            notes.append("需先确认付款规则，避免给出无法兑现的时点承诺。")
        if episode.workflow_stage == "rebate_negotiation":
            notes.append("优先解释利润压力，再谈返点目标。")
        if episode.workflow_stage == "price_negotiation":
            notes.append("若达人强边界，优先换权益而不是强压低价。")
        return dedupe_keep_order(notes)

    def _find_next_agency_reply(
        self,
        messages: list[ConversationMessage],
        start_idx: int,
    ) -> ConversationMessage | None:
        for message in messages[start_idx + 1:]:
            if message.role == "creator":
                return None
            if message.role == "agency":
                return message
        return None

    def _build_episode_filter_tags(self, episode: NegotiationEpisode) -> list[str]:
        tags = [
            f"workflow_stage:{episode.workflow_stage}",
            f"episode_goal:{episode.episode_goal}",
            f"objection_type:{episode.objection_type}",
            f"knowledge_base:{episode.knowledge_base}",
            f"outcome:{episode.outcome}",
            f"rebate_target_status:{episode.rebate_target_status}",
            f"agency_margin_pressure:{episode.agency_margin_pressure}",
            f"rights_gap_status:{episode.rights_gap_status}",
            f"payment_blocker_type:{episode.payment_blocker_type}",
        ]
        for trait in episode.creator_traits:
            tags.append(f"{trait.trait_name}:{trait.value}")
        if episode.current_rebate_rate is not None:
            tags.append(f"current_rebate_rate:{int(round(episode.current_rebate_rate * 100))}")
        if episode.target_rebate_rate is not None:
            tags.append(f"target_rebate_rate:{int(round(episode.target_rebate_rate * 100))}")
        if episode.listed_price is not None:
            tags.append(f"listed_price:{int(episode.listed_price)}")
        if episode.target_price is not None:
            tags.append(f"target_price:{int(episode.target_price)}")
        return dedupe_keep_order(tags)

    def _map_sft_bucket(self, workflow_stage: str) -> str:
        for bucket, stages in SFT_BUCKETS.items():
            if workflow_stage in stages:
                return bucket
        return "execution"

    def _build_episode_chunk_text(
        self,
        episode: NegotiationEpisode,
        message_map: dict[str, ConversationMessage],
    ) -> str:
        lines = [
            f"workflow_stage: {episode.workflow_stage}",
            f"episode_goal: {episode.episode_goal}",
            f"objection_type: {episode.objection_type}",
            f"creator_response_type: {episode.creator_response_type}",
            f"outcome: {episode.outcome}",
            f"summary: {episode.summary}",
        ]
        if episode.listed_price is not None:
            lines.append(f"listed_price: {episode.listed_price}")
        if episode.target_price is not None:
            lines.append(f"target_price: {episode.target_price}")
        if episode.current_rebate_rate is not None:
            lines.append(f"current_rebate_rate: {episode.current_rebate_rate}")
        if episode.target_rebate_rate is not None:
            lines.append(f"target_rebate_rate: {episode.target_rebate_rate}")
        if episode.creator_traits:
            lines.append(
                "creator_traits: "
                + " | ".join(f"{trait.trait_name}={trait.value}" for trait in episode.creator_traits)
            )
        for message_id in episode.message_ids:
            message = message_map[message_id]
            lines.append(f"{message.role}: {message.clean_text}")
        return "\n".join(lines)
