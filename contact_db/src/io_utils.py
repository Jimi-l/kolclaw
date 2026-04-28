
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterator, List

from .schemas import (
    NormalizedConversation,
    NormalizedMessage,
    TalkTemplate,
    TrainingSample,
    ConversationTurn,
)


def list_json_files(input_dir: str | Path, skip_dirs: List[str] | None = None) -> List[Path]:
    if skip_dirs is None:
        skip_dirs = ["outputs", "docs", "src", "scripts", "__pycache__", ".git", ".venv"]
    skip_dirs = [d.lower() for d in skip_dirs]

    input_path = Path(input_dir)
    json_files: List[Path] = []

    if not input_path.exists():
        return json_files

    for item in input_path.iterdir():
        if item.is_dir() and item.name.lower() in skip_dirs:
            continue
        if item.is_file() and item.suffix.lower() == ".json":
            json_files.append(item)

    return sorted(json_files)


def load_json(file_path: str | Path) -> Dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def append_jsonl(file_path: str | Path, data: Dict[str, Any]):
    with open(file_path, "a", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False))
        f.write("\n")


def write_jsonl(file_path: str | Path, items: Iterator[Dict[str, Any]]):
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False))
            f.write("\n")


def write_conversations_jsonl(file_path: str | Path, conversations: List[NormalizedConversation]):
    def item_iter():
        for conv in conversations:
            yield conv.to_dict(include_messages=False)

    write_jsonl(file_path, item_iter())


def write_messages_jsonl(file_path: str | Path, conversations: List[NormalizedConversation]):
    def item_iter():
        for conv in conversations:
            for msg in conv.messages:
                yield msg.to_dict()

    write_jsonl(file_path, item_iter())


def write_turns_jsonl(file_path: str | Path, turns: List[ConversationTurn]):
    def item_iter():
        for turn in turns:
            yield turn.to_dict()

    write_jsonl(file_path, item_iter())


def write_samples_jsonl(file_path: str | Path, samples: List[TrainingSample]):
    def item_iter():
        for sample in samples:
            yield sample.to_dict()

    write_jsonl(file_path, item_iter())


def write_templates_jsonl(file_path: str | Path, templates: List[TalkTemplate]):
    def item_iter():
        for tpl in templates:
            yield tpl.to_dict()

    write_jsonl(file_path, item_iter())


def write_templates_csv(file_path: str | Path, templates: List[TalkTemplate]):
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(TalkTemplate.csv_header())
        for tpl in templates:
            writer.writerow(tpl.to_csv_row())


def write_report(
    file_path: str | Path,
    input_files: List[Path],
    conversations: List[NormalizedConversation],
    turns: List[ConversationTurn],
    train_samples: List[TrainingSample],
    review_samples: List[TrainingSample],
    excluded_samples: List[TrainingSample],
    templates: List[TalkTemplate],
    warnings: List[str],
):
    Path(file_path).parent.mkdir(parents=True, exist_ok=True)

    total_raw_messages = sum(c.message_count_raw for c in conversations)
    total_normalized_messages = sum(c.message_count_normalized for c in conversations)
    non_text_messages = sum(1 for c in conversations for m in c.messages if not m.is_text)

    all_samples = train_samples + review_samples + excluded_samples

    with open(file_path, "w", encoding="utf-8") as f:
        f.write("# Pipeline Report\n\n")

        f.write("## Summary\n\n")
        f.write(f"- Input files: {len(input_files)}\n")
        f.write(f"- Conversations: {len(conversations)}\n")
        f.write(f"- Raw messages: {total_raw_messages}\n")
        f.write(f"- Normalized messages: {total_normalized_messages}\n")
        f.write(f"- Non-text messages: {non_text_messages}\n")
        f.write(f"- Conversation turns: {len(turns)}\n")
        f.write(f"- Total samples: {len(all_samples)}\n")
        f.write(f"  - Trainable: {len(train_samples)}\n")
        f.write(f"  - Needs review: {len(review_samples)}\n")
        f.write(f"  - Excluded: {len(excluded_samples)}\n")
        f.write(f"- Template candidates: {len(templates)}\n\n")

        f.write("## Exclusion Reasons\n\n")
        from collections import defaultdict
        reason_counts: defaultdict[str, int] = defaultdict(int)
        for s in excluded_samples:
            if s.exclusion_reason:
                reason_counts[s.exclusion_reason.value] += 1
        for reason, count in sorted(reason_counts.items()):
            f.write(f"- {reason}: {count}\n")
        f.write("\n")

        f.write("## Input Files\n\n")
        for fp in input_files:
            f.write(f"- {fp.name}\n")
        f.write("\n")

        f.write("## Warnings\n\n")
        if warnings:
            for w in warnings:
                f.write(f"- {w}\n")
        else:
            f.write("No warnings.\n")
        f.write("\n")

        f.write("## Template Top 10 (by reusable_score)\n\n")
        for i, tpl in enumerate(templates[:10]):
            f.write(f"{i+1}. (reusable={tpl.reusable_score:.2f}, value={tpl.business_value_score:.2f}, n={tpl.count})\n")
            f.write(f"   {tpl.template_text}\n\n")

