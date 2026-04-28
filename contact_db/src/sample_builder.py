
from __future__ import annotations

from typing import List

from .schemas import (
    ContextMessage,
    ConversationTurn,
    NormalizedConversation,
    NormalizedMessage,
    Role,
    Stage,
    Scene,
    CreatorIntent,
    AgencyIntent,
    Tone,
    Outcome,
    LabelSource,
    generate_turn_id,
    generate_sample_id,
    TrainingSample,
)


def merge_consecutive_same_role_messages(
    messages: List[NormalizedMessage],
    merge_window_seconds: int = 300,
) -> List[NormalizedMessage]:
    if not messages:
        return []

    merged: List[NormalizedMessage] = []
    current_group: List[NormalizedMessage] = [messages[0]]
    current_role = messages[0].role

    for msg in messages[1:]:
        time_diff = msg.create_time - current_group[-1].create_time
        if msg.role == current_role and time_diff <= merge_window_seconds:
            current_group.append(msg)
        else:
            merged.append(_merge_group(current_group))
            current_group = [msg]
            current_role = msg.role

    if current_group:
        merged.append(_merge_group(current_group))

    return merged


def _merge_group(group: List[NormalizedMessage]) -> NormalizedMessage:
    if len(group) == 1:
        return group[0]

    first = group[0]
    last = group[-1]

    content_parts = []
    for msg in group:
        if msg.content_masked:
            content_parts.append(msg.content_masked)
    merged_content = "\n".join(content_parts)

    quality_flags = list(set().union(*[m.quality_flags for m in group]))
    source_message_ids: List[str] = []
    source_seq_nums: List[int] = []
    for msg in group:
        source_message_ids.extend(msg.source_message_ids or [msg.message_id])
        source_seq_nums.extend(msg.source_seq_nums or [msg.seq_num])

    return NormalizedMessage(
        message_id=first.message_id,
        conversation_id=first.conversation_id,
        seq_num=first.seq_num,
        create_time=first.create_time,
        formatted_time=first.formatted_time,
        role=first.role,
        role_inference_source=first.role_inference_source,
        role_confidence=first.role_confidence,
        message_type=first.message_type,
        is_text=all(m.is_text for m in group),
        content_masked=merged_content,
        sender_id_hash=first.sender_id_hash,
        sender_display_name_masked=first.sender_display_name_masked,
        platform_message_id_hash=first.platform_message_id_hash,
        quality_flags=quality_flags,
        source_message_ids=source_message_ids,
        source_seq_nums=source_seq_nums,
        start_time=first.start_time or first.create_time,
        end_time=last.end_time or last.create_time,
    )


class ConversationTurnBuilder:
    def __init__(
        self,
        merge_window_seconds: int = 300,
        context_window_size: int = 6,
    ):
        self.merge_window_seconds = merge_window_seconds
        self.context_window_size = context_window_size

    def build_turns(
        self,
        conversation: NormalizedConversation,
    ) -> List[ConversationTurn]:
        turns: List[ConversationTurn] = []

        original_messages = conversation.messages
        if not original_messages:
            return turns

        merged_messages = merge_consecutive_same_role_messages(
            original_messages,
            self.merge_window_seconds
        )

        turn_idx = 0
        for idx, msg in enumerate(merged_messages):
            if msg.role != Role.CREATOR or not msg.is_text:
                continue

            next_agency_msg = None
            for j in range(idx + 1, len(merged_messages)):
                candidate = merged_messages[j]
                if candidate.role == Role.CREATOR:
                    break
                if candidate.role == Role.AGENCY and candidate.is_text:
                    next_agency_msg = candidate
                    break

            if next_agency_msg is None:
                continue

            context_messages = self._collect_context(merged_messages, idx)

            turn = ConversationTurn(
                turn_id=generate_turn_id(conversation.conversation_id, turn_idx),
                conversation_id=conversation.conversation_id,
                creator_message=msg,
                agency_reply=next_agency_msg,
                context_messages=context_messages,
                stage=Stage.UNKNOWN,
                scene=Scene.UNKNOWN,
                creator_intent=CreatorIntent.UNKNOWN,
                agency_intent=AgencyIntent.UNKNOWN,
                tone=Tone.NEUTRAL,
                outcome=Outcome.UNKNOWN,
                label_source=LabelSource.RULE_BASED,
                needs_review=False,
            )
            turns.append(turn)
            turn_idx += 1

        return turns

    def _collect_context(
        self,
        messages: List[NormalizedMessage],
        creator_idx: int,
    ) -> List[ContextMessage]:
        start_idx = max(0, creator_idx - self.context_window_size)
        context_messages: List[ContextMessage] = []

        for i in range(start_idx, creator_idx):
            msg = messages[i]
            context_messages.append(
                ContextMessage(
                    message_id=msg.message_id,
                    role=msg.role.value,
                    content_masked=msg.content_masked,
                    create_time=msg.create_time,
                )
            )

        return context_messages


class TrainingSampleBuilder:
    def __init__(self):
        pass

    def build_samples(
        self,
        turns: List[ConversationTurn],
    ) -> List[TrainingSample]:
        samples: List[TrainingSample] = []

        sample_idx = 0
        for turn in turns:
            if not turn.creator_message.is_text or not turn.agency_reply.is_text:
                continue

            quality_flags: List[str] = []
            if len(turn.creator_message.content_masked) < 3:
                quality_flags.append("short_creator_message")
            if len(turn.agency_reply.content_masked) < 3:
                quality_flags.append("short_agency_reply")

            quality_score = 0.5
            if turn.stage != Stage.UNKNOWN and turn.scene != Scene.UNKNOWN:
                quality_score += 0.2
            if not quality_flags:
                quality_score += 0.1
            quality_score = min(1.0, quality_score)

            sample = TrainingSample(
                sample_id=generate_sample_id(turn.conversation_id, sample_idx),
                conversation_id=turn.conversation_id,
                turn_id=turn.turn_id,
                stage=turn.stage,
                scene=turn.scene,
                context_messages=turn.context_messages,
                creator_message=turn.creator_message.content_masked,
                agency_reply=turn.agency_reply.content_masked,
                creator_intent=turn.creator_intent,
                agency_intent=turn.agency_intent,
                tone=turn.tone,
                outcome=turn.outcome,
                template_candidate=None,
                quality_score=quality_score,
                needs_review=turn.needs_review,
                quality_flags=quality_flags,
                source_message_ids=(
                    (turn.creator_message.source_message_ids or [turn.creator_message.message_id])
                    + (turn.agency_reply.source_message_ids or [turn.agency_reply.message_id])
                ),
                source_seq_nums=(
                    (turn.creator_message.source_seq_nums or [turn.creator_message.seq_num])
                    + (turn.agency_reply.source_seq_nums or [turn.agency_reply.seq_num])
                ),
            )
            samples.append(sample)
            sample_idx += 1

        return samples
