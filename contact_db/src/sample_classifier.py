
from __future__ import annotations

import re
from typing import List, Tuple

from .schemas import (
    BusinessRelevance,
    ExclusionReason,
    SampleStatus,
    TrainingSample,
    Scene,
    CreatorIntent,
    AgencyIntent,
)
from .normalizer import is_business_relevant


class SampleClassifier:
    def __init__(
        self,
        min_content_length: int = 5,
        min_quality_score_for_train: float = 0.7,
    ):
        self.min_content_length = min_content_length
        self.min_quality_score_for_train = min_quality_score_for_train

    def classify_samples(
        self,
        samples: List[TrainingSample],
    ) -> Tuple[List[TrainingSample], List[TrainingSample], List[TrainingSample]]:
        train_samples: List[TrainingSample] = []
        review_samples: List[TrainingSample] = []
        excluded_samples: List[TrainingSample] = []

        for sample in samples:
            self._classify_single_sample(sample)

            if sample.sample_status == SampleStatus.TRAINABLE:
                train_samples.append(sample)
            elif sample.sample_status == SampleStatus.NEEDS_REVIEW:
                review_samples.append(sample)
            else:
                excluded_samples.append(sample)

        return train_samples, review_samples, excluded_samples

    def _classify_single_sample(self, sample: TrainingSample):
        combined_text = sample.creator_message + " " + sample.agency_reply

        if is_business_relevant(combined_text):
            sample.business_relevance = BusinessRelevance.BUSINESS
        else:
            sample.business_relevance = BusinessRelevance.NON_BUSINESS

        if not sample.source_message_ids:
            sample.source_message_ids = self._extract_source_message_ids(sample)

        exclusion_reason = self._check_exclusion(sample)
        if exclusion_reason is not None:
            sample.exclusion_reason = exclusion_reason
            sample.sample_status = SampleStatus.EXCLUDED
            return

        if self._should_go_to_review(sample):
            sample.sample_status = SampleStatus.NEEDS_REVIEW
            sample.needs_review = True
            return

        if sample.quality_score >= self.min_quality_score_for_train:
            sample.sample_status = SampleStatus.TRAINABLE
            sample.needs_review = False
        else:
            sample.sample_status = SampleStatus.NEEDS_REVIEW
            sample.needs_review = True

    def _extract_source_message_ids(self, sample: TrainingSample) -> List[str]:
        ids: List[str] = []
        for cm in sample.context_messages:
            ids.append(cm.message_id)
        return ids

    def _check_exclusion(self, sample: TrainingSample) -> ExclusionReason | None:
        if sample.business_relevance == BusinessRelevance.NON_BUSINESS:
            if sample.scene == Scene.SMALL_TALK or sample.creator_intent == CreatorIntent.SMALL_TALK:
                return ExclusionReason.NON_BUSINESS_SMALL_TALK

        creator_len = len(sample.creator_message.strip())
        agency_len = len(sample.agency_reply.strip())
        if creator_len < self.min_content_length or agency_len < self.min_content_length:
            return ExclusionReason.SHORT_CONTENT

        if self._is_only_link(sample.creator_message) or self._is_only_link(sample.agency_reply):
            return ExclusionReason.ONLY_LINK

        if self._is_only_emoji(sample.creator_message) or self._is_only_emoji(sample.agency_reply):
            return ExclusionReason.ONLY_EMOJI

        if "non_text" in sample.quality_flags:
            return ExclusionReason.NON_TEXT_ONLY

        return None

    def _should_go_to_review(self, sample: TrainingSample) -> bool:
        if sample.stage.value == "unknown" and sample.business_relevance == BusinessRelevance.BUSINESS:
            return True

        if sample.scene.value == "unknown" and sample.business_relevance == BusinessRelevance.BUSINESS:
            return True

        if sample.quality_flags:
            return True

        return False

    def _is_only_link(self, text: str) -> bool:
        text = text.strip()
        url_pattern = re.compile(r"^https?://[^\s]+$")
        return bool(url_pattern.match(text))

    def _is_only_emoji(self, text: str) -> bool:
        text = text.strip()
        if not text:
            return False
        emoji_chars = set()
        for c in text:
            if not c.isspace():
                emoji_chars.add(c)
        non_word_chars = all(
            not (c.isalnum() or c in [",", ".", "!", "?", "，", "。", "！", "？"])
            for c in emoji_chars
        )
        return non_word_chars and len(emoji_chars) <= 10
