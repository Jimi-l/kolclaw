#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


MEDIA_NAME = "小被罩儿"
CREATOR_CODES = ["智能路障", "张开", "Monkey", "肉鸽三缺一", "阿一&秦观南"]
CREATOR_LABEL_HINTS = {
    "智能路障": ["智能路障"],
    "张开": ["张开"],
    "Monkey": ["Monkey", "monkey"],
    "肉鸽三缺一": ["肉鸽三缺一"],
    "阿一&秦观南": ["阿一", "秦观南", "阿一&秦观南"],
}
SPEAKER_LINE_PATTERN = re.compile(r"^(.*): (.*)$")
HEADER_PATTERN = re.compile(r"^\[转发的聊天记录\]")


@dataclass
class ParsedMessage:
    seq_num: int
    role: str
    speaker: str
    text: str
    source_line_start: int
    source_line_end: int

    def to_dict(self) -> dict:
        return {
            "seq_num": self.seq_num,
            "role": self.role,
            "speaker": self.speaker,
            "text": self.text,
            "source_line_start": self.source_line_start,
            "source_line_end": self.source_line_end,
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="清洗文件传输助手中的合并转发聊天记录，并重建为建联话术库可用输入。"
    )
    parser.add_argument(
        "--input-file",
        "-i",
        type=str,
        default="data/私聊_文件传输助手.json",
        help="待清洗的 WeFlow JSON 文件",
    )
    parser.add_argument(
        "--output-dir",
        "-o",
        type=str,
        default="outputs/file_transfer_assistant_cleaned",
        help="清洗结果输出目录",
    )
    return parser.parse_args()


def load_raw_content(file_path: Path) -> tuple[dict, list[str]]:
    with file_path.open("r", encoding="utf-8") as f:
        raw_data = json.load(f)

    messages = raw_data.get("messages", [])
    if len(messages) != 1:
        raise ValueError(
            f"期望输入只有 1 条合并转发消息，实际为 {len(messages)} 条。"
        )

    content = messages[0].get("content")
    if not isinstance(content, str):
        raise ValueError("messages[0].content 不是字符串，无法清洗。")

    return raw_data, content.splitlines()


def normalize_alias(text: str) -> str:
    normalized = re.sub(r"[\s\u2005\u3000._。·、-]+", "", text).strip().lower()
    return normalized


def parse_speaker_line(line: str) -> tuple[str | None, str | None]:
    match = SPEAKER_LINE_PATTERN.match(line)
    if not match:
        return None, None
    speaker = match.group(1).strip()
    text = match.group(2)
    return speaker, text


def next_non_empty_index(lines: list[str], start: int) -> int | None:
    for idx in range(start, len(lines)):
        if lines[idx].strip():
            return idx
    return None


def find_segment_boundaries(lines: list[str]) -> list[tuple[str, int]]:
    boundaries: list[tuple[str, int]] = []
    alias_idx = 0

    for idx, line in enumerate(lines):
        if alias_idx >= len(CREATOR_CODES) - 1:
            break

        speaker, text = parse_speaker_line(line)
        if speaker != MEDIA_NAME or text is None:
            continue

        expected_alias = CREATOR_CODES[alias_idx]
        if normalize_alias(text) != normalize_alias(expected_alias):
            continue

        next_idx = next_non_empty_index(lines, idx + 1)
        if next_idx is None:
            continue

        next_speaker, _ = parse_speaker_line(lines[next_idx])
        if next_speaker is None:
            continue

        boundaries.append((expected_alias, idx))
        alias_idx += 1

    if len(boundaries) != len(CREATOR_CODES) - 1:
        raise ValueError(
            f"只识别到 {len(boundaries)} 个分段锚点，期望 {len(CREATOR_CODES) - 1} 个。"
        )

    return boundaries


def infer_creator_wechat_name(segment_lines: Iterable[str]) -> str:
    speaker_counts: Counter[str] = Counter()
    for line in segment_lines:
        speaker, _ = parse_speaker_line(line)
        if speaker and speaker != MEDIA_NAME:
            speaker_counts[speaker] += 1

    if not speaker_counts:
        raise ValueError("当前分段中没有识别到达人侧发言人。")

    return speaker_counts.most_common(1)[0][0]


def append_line(base: str, line: str) -> str:
    if not base:
        return line
    return f"{base}\n{line}"


def clean_message_text(text: str) -> str:
    return text.strip()


def parse_segment_messages(
    lines: list[str],
    start_line: int,
    end_line: int,
    creator_wechat_name: str,
) -> tuple[list[ParsedMessage], list[str]]:
    messages: list[ParsedMessage] = []
    notes: list[str] = []

    current_speaker: str | None = None
    current_text = ""
    current_start = start_line
    current_end = start_line
    seq_num = 1
    unexpected_speakers: Counter[str] = Counter()

    def flush_current() -> None:
        nonlocal current_speaker, current_text, current_start, current_end, seq_num

        if current_speaker is None:
            return

        text = clean_message_text(current_text)
        if not text:
            current_speaker = None
            current_text = ""
            return

        if current_speaker == MEDIA_NAME and text == MEDIA_NAME:
            notes.append(
                f"移除了疑似归档噪音消息：第 {current_start}-{current_end} 行内容为“小被罩儿”。"
            )
        else:
            role = "agency" if current_speaker == MEDIA_NAME else "creator"
            messages.append(
                ParsedMessage(
                    seq_num=seq_num,
                    role=role,
                    speaker=current_speaker,
                    text=text,
                    source_line_start=current_start,
                    source_line_end=current_end,
                )
            )
            seq_num += 1

        current_speaker = None
        current_text = ""

    for line_idx in range(start_line, end_line + 1):
        line = lines[line_idx]
        if HEADER_PATTERN.match(line.strip()):
            notes.append(f"忽略源头标题行：第 {line_idx} 行 `{line.strip()}`。")
            continue

        speaker, text = parse_speaker_line(line)
        if speaker in {MEDIA_NAME, creator_wechat_name}:
            flush_current()
            current_speaker = speaker
            current_text = text or ""
            current_start = line_idx
            current_end = line_idx
            continue

        if speaker and speaker not in {MEDIA_NAME, creator_wechat_name}:
            unexpected_speakers[speaker] += 1

        if current_speaker is None:
            notes.append(f"发现孤立续行，已忽略：第 {line_idx} 行 `{line}`。")
            continue

        current_text = append_line(current_text, line)
        current_end = line_idx

    flush_current()

    if unexpected_speakers:
        notes.append(
            "发现非主对话发言人，已按续行并入上一条消息："
            + ", ".join(
                f"{speaker} x{count}"
                for speaker, count in unexpected_speakers.most_common()
            )
        )

    return messages, notes


def build_segments(lines: list[str]) -> list[dict]:
    boundaries = find_segment_boundaries(lines)
    segments: list[dict] = []

    segment_start = 0
    for alias_idx, creator_code in enumerate(CREATOR_CODES):
        if alias_idx < len(boundaries):
            _, boundary_line = boundaries[alias_idx]
            segment_end = boundary_line - 1
            boundary_marker_line = boundary_line
        else:
            segment_end = len(lines) - 1
            boundary_marker_line = None

        segment_lines = lines[segment_start : segment_end + 1]
        creator_wechat_name = infer_creator_wechat_name(segment_lines)
        messages, notes = parse_segment_messages(
            lines=lines,
            start_line=segment_start,
            end_line=segment_end,
            creator_wechat_name=creator_wechat_name,
        )

        segments.append(
            {
                "conversation_index": alias_idx + 1,
                "creator_code": creator_code,
                "label_hints": CREATOR_LABEL_HINTS.get(creator_code, [creator_code]),
                "creator_wechat_name": creator_wechat_name,
                "media_wechat_name": MEDIA_NAME,
                "source_line_start": segment_start,
                "source_line_end": segment_end,
                "boundary_marker_line": boundary_marker_line,
                "message_count": len(messages),
                "messages": messages,
                "notes": notes,
            }
        )

        if boundary_marker_line is None:
            break
        segment_start = boundary_marker_line + 1

    if len(segments) != len(CREATOR_CODES):
        raise ValueError(f"最终只拆出了 {len(segments)} 段会话，期望 {len(CREATOR_CODES)} 段。")

    return segments


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(file_path: Path, payload: dict | list) -> None:
    with file_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def write_jsonl(file_path: Path, rows: Iterable[dict]) -> None:
    with file_path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False))
            f.write("\n")


def to_cleaned_conversation_record(source_file: Path, segment: dict) -> dict:
    return {
        "source_file": source_file.name,
        "conversation_index": segment["conversation_index"],
        "creator_code": segment["creator_code"],
        "label_hints": segment["label_hints"],
        "creator_wechat_name": segment["creator_wechat_name"],
        "media_wechat_name": segment["media_wechat_name"],
        "source_line_start": segment["source_line_start"],
        "source_line_end": segment["source_line_end"],
        "boundary_marker_line": segment["boundary_marker_line"],
        "message_count": segment["message_count"],
        "messages": [message.to_dict() for message in segment["messages"]],
        "notes": segment["notes"],
    }


def build_reconstructed_weflow(
    source_file: Path,
    raw_data: dict,
    segment: dict,
    conversation_start_ts: int,
) -> dict:
    messages = []
    for idx, message in enumerate(segment["messages"], start=1):
        create_time = conversation_start_ts + (idx - 1) * 301
        formatted_time = datetime.fromtimestamp(create_time).strftime("%Y-%m-%d %H:%M:%S")
        is_send = 1 if message.role == "agency" else 0
        sender_username = (
            f"agency_{normalize_alias(MEDIA_NAME)}"
            if is_send == 1
            else f"creator_{normalize_alias(segment['creator_code'])}"
        )

        messages.append(
            {
                "localId": idx,
                "createTime": create_time,
                "formattedTime": formatted_time,
                "type": "文本消息",
                "localType": 1,
                "content": message.text,
                "isSend": is_send,
                "senderUsername": sender_username,
                "senderDisplayName": message.speaker,
                "source": source_file.name,
                "senderAvatarKey": sender_username,
                "platformMessageId": f"{normalize_alias(segment['creator_code'])}_{idx:04d}",
            }
        )

    weflow_meta = raw_data.get("weflow", {})
    return {
        "weflow": {
            "version": weflow_meta.get("version", "forwarded-cleaner.v1"),
            "exportedAt": weflow_meta.get("exportedAt", 0),
            "generator": "clean_forwarded_file_assistant",
        },
        "session": {
            "wxid": f"forwarded_{normalize_alias(segment['creator_code'])}",
            "nickname": segment["creator_wechat_name"],
            "remark": segment["creator_code"],
            "displayName": segment["creator_wechat_name"],
            "type": "friend",
            "lastTimestamp": messages[-1]["createTime"] if messages else conversation_start_ts,
            "messageCount": len(messages),
            "avatar": "",
        },
        "messages": messages,
        "avatars": {},
    }


def write_outputs(source_file: Path, raw_data: dict, output_dir: Path, segments: list[dict]) -> None:
    ensure_dir(output_dir)
    reconstructed_dir = output_dir / "reconstructed_weflow"
    ensure_dir(reconstructed_dir)

    cleaned_conversations = [
        to_cleaned_conversation_record(source_file, segment)
        for segment in segments
    ]
    cleaned_messages = []
    for segment in cleaned_conversations:
        for message in segment["messages"]:
            cleaned_messages.append(
                {
                    "source_file": segment["source_file"],
                    "conversation_index": segment["conversation_index"],
                    "creator_code": segment["creator_code"],
                    "creator_wechat_name": segment["creator_wechat_name"],
                    "media_wechat_name": segment["media_wechat_name"],
                    **message,
                }
            )

    write_json(output_dir / "cleaned_conversations.json", cleaned_conversations)
    write_jsonl(output_dir / "cleaned_conversations.jsonl", cleaned_conversations)
    write_jsonl(output_dir / "cleaned_messages.jsonl", cleaned_messages)

    base_ts = raw_data.get("messages", [{}])[0].get("createTime", 0) or 1776909835
    for idx, segment in enumerate(segments):
        conv_start_ts = base_ts + idx * 100000
        reconstructed = build_reconstructed_weflow(
            source_file=source_file,
            raw_data=raw_data,
            segment=segment,
            conversation_start_ts=conv_start_ts,
        )
        filename = f"{idx + 1:02d}_{segment['creator_code']}.json"
        write_json(reconstructed_dir / filename, reconstructed)

    write_summary(output_dir / "cleaning_summary.md", cleaned_conversations)


def write_summary(file_path: Path, cleaned_conversations: list[dict]) -> None:
    with file_path.open("w", encoding="utf-8") as f:
        f.write("# 文件传输助手聊天记录清洗摘要\n\n")
        f.write("## 达人映射\n\n")
        f.write("| 顺序 | 达人代号 | 文件内标签线索 | 实际微信名 | 消息数 | 原始行范围 |\n")
        f.write("| --- | --- | --- | --- | ---: | --- |\n")
        for conv in cleaned_conversations:
            f.write(
                f"| {conv['conversation_index']} | {conv['creator_code']} | "
                f"{' / '.join(conv['label_hints'])} | {conv['creator_wechat_name']} | {conv['message_count']} | "
                f"{conv['source_line_start']}-{conv['source_line_end']} |\n"
            )

        f.write("\n## 清洗说明\n\n")
        f.write(f"- 媒介统一识别为 `{MEDIA_NAME}`。\n")
        f.write("- 按用户确认的规则切分：达人标签消息出现在该达人会话之后。\n")
        f.write("- 只保留媒介与单一达人之间的真实发言顺序，归档标题和明显噪音标签会被剔除。\n")
        f.write("- `reconstructed_weflow/` 下的 5 个 JSON 可直接作为现有 pipeline 输入。\n")

        f.write("\n## 备注\n\n")
        for conv in cleaned_conversations:
            if not conv["notes"]:
                continue
            f.write(f"### {conv['creator_code']}\n\n")
            for note in conv["notes"]:
                f.write(f"- {note}\n")
            f.write("\n")


def main() -> None:
    args = parse_args()

    project_root = Path(__file__).resolve().parent.parent
    input_file = (project_root / args.input_file).resolve()
    output_dir = (project_root / args.output_dir).resolve()

    raw_data, lines = load_raw_content(input_file)
    segments = build_segments(lines)
    write_outputs(input_file, raw_data, output_dir, segments)

    print("=" * 60)
    print("文件传输助手聊天记录清洗完成")
    print("=" * 60)
    print(f"输入文件: {input_file}")
    print(f"输出目录: {output_dir}")
    print(f"拆分会话数: {len(segments)}")
    for segment in segments:
        print(
            f"- {segment['creator_code']} -> {segment['creator_wechat_name']} "
            f"({segment['message_count']} 条消息)"
        )


if __name__ == "__main__":
    main()
