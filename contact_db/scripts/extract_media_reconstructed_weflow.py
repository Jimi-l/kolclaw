#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


GENERIC_COUNTERPARTY_SPEAKERS = {".", "001"}
HEADER_PATTERN = re.compile(r"^\[转发的聊天记录\]")
SPEAKER_LINE_PATTERN = re.compile(r"^(.*?):\s?(.*)$")


@dataclass(frozen=True)
class LineRange:
    start: int
    end: int


@dataclass(frozen=True)
class ConversationSpec:
    creator_code: str
    counterparty_speakers: tuple[str, ...]
    ranges: tuple[LineRange, ...]
    session_display_name: str | None = None
    notes: tuple[str, ...] = ()


@dataclass
class ParsedMessage:
    role: str
    speaker: str
    text: str
    source_line_start: int
    source_line_end: int


@dataclass
class ExtractedConversation:
    media_name: str
    creator_code: str
    session_display_name: str
    counterparty_speakers: tuple[str, ...]
    source_file: str
    ranges: tuple[LineRange, ...]
    messages: list[ParsedMessage]
    notes: list[str] = field(default_factory=list)


def normalize_alias(text: str) -> str:
    return re.sub(r"[\s\u2005\u3000._。·、:：()（）【】\\/-]+", "", text).strip().lower()


def ensure_dir(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def write_json(file_path: Path, payload: dict | list) -> None:
    with file_path.open("w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, indent=2)


def strip_forward_marker(line: str) -> str:
    if line.startswith("= =: "):
        return line[5:]
    return line


def parse_speaker_line(line: str) -> tuple[str | None, str | None]:
    stripped = strip_forward_marker(line)
    match = SPEAKER_LINE_PATTERN.match(stripped)
    if not match:
        return None, None
    return match.group(1).strip(), match.group(2)


def append_text(base: str, line: str) -> str:
    if not base:
        return line
    return f"{base}\n{line}"


def clean_text(text: str) -> str:
    return text.strip()


def choose_session_display_name(spec: ConversationSpec) -> str:
    if spec.session_display_name:
        return spec.session_display_name
    return spec.creator_code


def speaker_display_name(raw_speaker: str, creator_code: str, media_name: str, role: str) -> str:
    if role == "agency":
        return media_name
    if raw_speaker in GENERIC_COUNTERPARTY_SPEAKERS:
        return creator_code
    return raw_speaker


def parse_conversation_messages(lines: list[str], media_name: str, spec: ConversationSpec) -> tuple[list[ParsedMessage], list[str]]:
    valid_speakers = {media_name, *spec.counterparty_speakers}
    messages: list[ParsedMessage] = []
    notes: list[str] = list(spec.notes)
    current_speaker: str | None = None
    current_text = ""
    current_start = -1
    current_end = -1

    def flush_current() -> None:
        nonlocal current_speaker, current_text, current_start, current_end

        if current_speaker is None:
            return

        text = clean_text(current_text)
        if text:
            role = "agency" if current_speaker == media_name else "creator"
            messages.append(
                ParsedMessage(
                    role=role,
                    speaker=current_speaker,
                    text=text,
                    source_line_start=current_start,
                    source_line_end=current_end,
                )
            )

        current_speaker = None
        current_text = ""
        current_start = -1
        current_end = -1

    for range_spec in spec.ranges:
        for line_idx in range(range_spec.start, range_spec.end + 1):
            raw_line = lines[line_idx]
            if HEADER_PATTERN.match(raw_line):
                notes.append(f"忽略转发标题行：第 {line_idx} 行。")
                continue

            normalized_line = strip_forward_marker(raw_line)
            speaker, text = parse_speaker_line(raw_line)
            if speaker in valid_speakers:
                flush_current()
                current_speaker = speaker
                current_text = text or ""
                current_start = line_idx
                current_end = line_idx
                continue

            if current_speaker is None:
                if normalized_line.strip():
                    notes.append(f"忽略孤立内容：第 {line_idx} 行 `{normalized_line[:60]}`。")
                continue

            current_text = append_text(current_text, normalized_line)
            current_end = line_idx

    flush_current()
    return messages, notes


def build_reconstructed_weflow(
    raw_data: dict,
    conversation: ExtractedConversation,
    conversation_index: int,
    base_timestamp: int,
) -> dict:
    session_display_name = conversation.session_display_name
    messages = []
    for idx, message in enumerate(conversation.messages, start=1):
        create_time = base_timestamp + (idx - 1) * 301
        formatted_time = datetime.fromtimestamp(create_time).strftime("%Y-%m-%d %H:%M:%S")
        is_send = 1 if message.role == "agency" else 0
        sender_username = (
            f"agency_{normalize_alias(conversation.media_name)}"
            if is_send
            else f"creator_{normalize_alias(conversation.creator_code)}"
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
                "senderDisplayName": speaker_display_name(
                    raw_speaker=message.speaker,
                    creator_code=conversation.creator_code,
                    media_name=conversation.media_name,
                    role=message.role,
                ),
                "source": conversation.source_file,
                "senderAvatarKey": sender_username,
                "platformMessageId": f"{normalize_alias(conversation.creator_code)}_{idx:04d}",
            }
        )

    weflow_meta = raw_data.get("weflow", {})
    return {
        "weflow": {
            "version": weflow_meta.get("version", "1.0.3"),
            "exportedAt": weflow_meta.get("exportedAt", 0),
            "generator": "extract_media_reconstructed_weflow",
        },
        "session": {
            "wxid": f"forwarded_{normalize_alias(conversation.media_name)}_{normalize_alias(conversation.creator_code)}",
            "nickname": session_display_name,
            "remark": conversation.creator_code,
            "displayName": session_display_name,
            "type": "friend",
            "lastTimestamp": messages[-1]["createTime"] if messages else base_timestamp,
            "messageCount": len(messages),
            "avatar": "",
        },
        "messages": messages,
        "avatars": {},
    }


def move_legacy_xiaobeizhao_files(reconstructed_root: Path) -> list[str]:
    media_dir = reconstructed_root / "小被罩儿"
    ensure_dir(media_dir)
    moved_files: list[str] = []
    for file_path in sorted(reconstructed_root.glob("*.json")):
        destination = media_dir / file_path.name
        if destination.exists():
            file_path.unlink()
            continue
        file_path.rename(destination)
        moved_files.append(file_path.name)
    return moved_files


def extract_batch(
    project_root: Path,
    media_name: str,
    input_file: Path,
    output_dir: Path,
    specs: tuple[ConversationSpec, ...],
) -> list[ExtractedConversation]:
    raw_data = json.loads(input_file.read_text(encoding="utf-8"))
    lines = raw_data["messages"][0]["content"].splitlines()
    ensure_dir(output_dir)

    base_ts = raw_data.get("messages", [{}])[0].get("createTime", 0) or 1776909835
    extracted: list[ExtractedConversation] = []

    for index, spec in enumerate(specs, start=1):
        messages, notes = parse_conversation_messages(lines, media_name, spec)
        conversation = ExtractedConversation(
            media_name=media_name,
            creator_code=spec.creator_code,
            session_display_name=choose_session_display_name(spec),
            counterparty_speakers=spec.counterparty_speakers,
            source_file=input_file.name,
            ranges=spec.ranges,
            messages=messages,
            notes=notes,
        )
        extracted.append(conversation)

        reconstructed = build_reconstructed_weflow(
            raw_data=raw_data,
            conversation=conversation,
            conversation_index=index,
            base_timestamp=base_ts + index * 100000,
        )
        filename = f"{index:02d}_{spec.creator_code}.json"
        write_json(output_dir / filename, reconstructed)

    return extracted


def write_summary(reconstructed_root: Path, moved_files: list[str], extracted_batches: dict[str, list[ExtractedConversation]]) -> None:
    summary_path = reconstructed_root / "extraction_summary.md"
    with summary_path.open("w", encoding="utf-8") as file:
        file.write("# 媒介聊天记录提取摘要\n\n")
        file.write("## 目录结构\n\n")
        for media_name in sorted(extracted_batches):
            file.write(f"- `{media_name}/`\n")
        if moved_files:
            file.write("\n")
            file.write(f"- 已将历史小被罩儿文件迁移到 `小被罩儿/`：{', '.join(moved_files)}\n")

        for media_name, conversations in extracted_batches.items():
            file.write(f"\n## {media_name}\n\n")
            file.write("| 文件 | 达人代号 | 对接微信名 | 源文件 | 源行范围 | 消息数 |\n")
            file.write("| --- | --- | --- | --- | --- | ---: |\n")
            for index, conversation in enumerate(conversations, start=1):
                ranges_text = " / ".join(f"{r.start}-{r.end}" for r in conversation.ranges)
                counterpart = " / ".join(conversation.counterparty_speakers)
                file.write(
                    f"| {index:02d}_{conversation.creator_code}.json | "
                    f"{conversation.creator_code} | {counterpart} | {conversation.source_file} | "
                    f"{ranges_text} | {len(conversation.messages)} |\n"
                )

            ambiguous = [
                conversation
                for conversation in conversations
                if conversation.creator_code != conversation.session_display_name
                or conversation.counterparty_speakers[0] != conversation.creator_code
            ]
            if ambiguous:
                file.write("\n### 映射说明\n\n")
                for conversation in ambiguous:
                    file.write(
                        f"- `{conversation.creator_code}` 文件按达人代号归档，"
                        f"消息对接方微信名为 `{' / '.join(conversation.counterparty_speakers)}`。\n"
                    )


def main() -> None:
    project_root = Path(__file__).resolve().parent.parent
    reconstructed_root = project_root / "outputs/file_transfer_assistant_cleaned/reconstructed_weflow"
    ensure_dir(reconstructed_root)

    moved_files = move_legacy_xiaobeizhao_files(reconstructed_root)

    y7_specs = (
        ConversationSpec("李狗蛋", ("李狗蛋",), (LineRange(1, 64),)),
        ConversationSpec("说游戏的涂涂", ("李狗蛋",), (LineRange(65, 84),)),
        ConversationSpec("大师兄阿诚（游戏解说）", ("李狗蛋",), (LineRange(85, 128), LineRange(195, 331))),
        ConversationSpec("游戏李狗蛋", ("李狗蛋",), (LineRange(129, 194),)),
        ConversationSpec("李白白", ("老白",), (LineRange(332, 633),)),
        ConversationSpec("陈某人", ("陈某人",), (LineRange(634, 742),)),
        ConversationSpec("考拉的除草证", ("001",), (LineRange(743, 791),)),
        ConversationSpec("什么洞洞幺🐹", ("001",), (LineRange(792, 906),)),
        ConversationSpec("大猫仙人", ("大猫仙人",), (LineRange(907, 993),)),
        ConversationSpec("谷仓里的耗子精", ("鸽几",), (LineRange(994, 1197),)),
        ConversationSpec("小鬼卡比", ("小鬼卡比",), (LineRange(1198, 1314),)),
        ConversationSpec("李啾啾", ("李JOJO（备注项目及来意）",), (LineRange(1315, 1484),)),
        ConversationSpec("虎纹章鱼", ("章鱼小商务（饭团🍙）",), (LineRange(1485, 1619),)),
        ConversationSpec("水星&佑崎Kizaki", (".",), (LineRange(1620, 1947),)),
    )

    extracted_batches = {
        "小被罩儿": [],
        "Y7": extract_batch(
            project_root=project_root,
            media_name="Y7",
            input_file=project_root / "data/私聊_微梦传媒&像素绽放的Tony华立辉.json",
            output_dir=reconstructed_root / "Y7",
            specs=y7_specs,
        ),
    }

    write_summary(reconstructed_root, moved_files, extracted_batches)

    print("=" * 60)
    print("媒介聊天记录提取完成")
    print("=" * 60)
    print(f"输出目录: {reconstructed_root}")
    if moved_files:
        print(f"已迁移小被罩儿历史文件: {', '.join(moved_files)}")
    for media_name, conversations in extracted_batches.items():
        if not conversations:
            continue
        print(f"\n[{media_name}]")
        for index, conversation in enumerate(conversations, start=1):
            print(
                f"- {index:02d}_{conversation.creator_code}.json | "
                f"{' / '.join(conversation.counterparty_speakers)} | "
                f"{len(conversation.messages)} 条消息"
            )


if __name__ == "__main__":
    main()
