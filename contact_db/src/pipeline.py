
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from .io_utils import (
    list_json_files,
    load_json,
    write_conversations_jsonl,
    write_messages_jsonl,
    write_turns_jsonl,
    write_samples_jsonl,
    write_templates_jsonl,
    write_templates_csv,
    write_report,
)
from .normalizer import WeFlowNormalizer, WeakLabeler
from .sample_builder import ConversationTurnBuilder, TrainingSampleBuilder
from .sample_classifier import SampleClassifier
from .schemas import NormalizedConversation, ConversationTurn, TrainingSample, TalkTemplate
from .template_builder import TemplateMiner
from .validator import WeFlowValidator, format_validation_errors


class TalkLibraryPipeline:
    def __init__(
        self,
        input_dir: str | Path,
        output_dir: str | Path,
        prefix: str = "demo",
    ):
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.prefix = prefix

        self.validator = WeFlowValidator()
        self.normalizer = WeFlowNormalizer()
        self.turn_builder = ConversationTurnBuilder()
        self.sample_builder = TrainingSampleBuilder()
        self.sample_classifier = SampleClassifier()
        self.template_miner = TemplateMiner()
        self.labeler = WeakLabeler()

        self.input_files: List[Path] = []
        self.conversations: List[NormalizedConversation] = []
        self.turns: List[ConversationTurn] = []
        self.all_samples: List[TrainingSample] = []
        self.train_samples: List[TrainingSample] = []
        self.review_samples: List[TrainingSample] = []
        self.excluded_samples: List[TrainingSample] = []
        self.templates: List[TalkTemplate] = []
        self.warnings: List[str] = []

    def run(self):
        self._setup_output_dir()
        self._discover_input_files()
        self._process_files()
        self._build_turns()
        self._label_turns()
        self._build_samples()
        self._classify_samples()
        self._mine_templates()
        self._write_outputs()
        self._write_report()

    def _setup_output_dir(self):
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _discover_input_files(self):
        self.input_files = list_json_files(self.input_dir)
        if not self.input_files:
            self.warnings.append(f"No JSON files found in {self.input_dir}")

    def _process_files(self):
        for file_path in self.input_files:
            try:
                raw_data = load_json(file_path)

                is_valid, validation_errors = self.validator.validate_file(
                    raw_data, file_path.name
                )
                if not is_valid:
                    error_strs = format_validation_errors(validation_errors)
                    self.warnings.extend([f"{file_path.name}: {e}" for e in error_strs])
                    self.warnings.append(f"{file_path.name}: Skipped due to validation errors")
                    continue

                conv, warnings = self.normalizer.normalize_conversation(
                    raw_data, file_path.name
                )
                self.conversations.append(conv)
                self.warnings.extend([f"{file_path.name}: {w}" for w in warnings])
            except Exception as e:
                self.warnings.append(f"{file_path.name}: Failed to process - {e}")

    def _build_turns(self):
        for conv in self.conversations:
            turns = self.turn_builder.build_turns(conv)
            self.turns.extend(turns)

    def _label_turns(self):
        for i in range(len(self.turns)):
            self.turns[i] = self.labeler.label_turn(self.turns[i])

    def _build_samples(self):
        self.all_samples = self.sample_builder.build_samples(self.turns)

    def _classify_samples(self):
        self.train_samples, self.review_samples, self.excluded_samples = (
            self.sample_classifier.classify_samples(self.all_samples)
        )

    def _mine_templates(self):
        self.templates = self.template_miner.mine_templates(self.train_samples)

    def _write_outputs(self):
        write_conversations_jsonl(
            self.output_dir / f"{self.prefix}_normalized_conversations.jsonl",
            self.conversations,
        )
        write_messages_jsonl(
            self.output_dir / f"{self.prefix}_normalized_messages.jsonl",
            self.conversations,
        )
        write_turns_jsonl(
            self.output_dir / f"{self.prefix}_conversation_turns.jsonl",
            self.turns,
        )
        write_samples_jsonl(
            self.output_dir / f"{self.prefix}_training_samples.jsonl",
            self.train_samples,
        )
        write_samples_jsonl(
            self.output_dir / f"{self.prefix}_review_samples.jsonl",
            self.review_samples,
        )
        write_samples_jsonl(
            self.output_dir / f"{self.prefix}_excluded_samples.jsonl",
            self.excluded_samples,
        )
        write_templates_jsonl(
            self.output_dir / f"{self.prefix}_template_candidates.jsonl",
            self.templates,
        )
        write_templates_csv(
            self.output_dir / f"{self.prefix}_template_candidates.csv",
            self.templates,
        )

    def _write_report(self):
        write_report(
            self.output_dir / f"{self.prefix}_pipeline_report.md",
            self.input_files,
            self.conversations,
            self.turns,
            self.train_samples,
            self.review_samples,
            self.excluded_samples,
            self.templates,
            self.warnings,
        )
