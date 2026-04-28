#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterable


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "nested_forwarded_chat_extraction"

SOURCE_CONFIGS = [
    {
        "name": "tony_forwarded",
        "label": "私聊_微梦传媒&像素绽放的Tony华立辉.json",
        "path": PROJECT_ROOT / "data" / "私聊_微梦传媒&像素绽放的Tony华立辉.json",
        "expected_count": 78,
    },
    {
        "name": "file_transfer_assistant",
        "label": "私聊_文件传输助手.json",
        "path": PROJECT_ROOT / "data" / "私聊_文件传输助手.json",
        "expected_count": 13,
    },
]

HEADER_PATTERN = re.compile(r"^\[转发的聊天记录\].*$")
SPEAKER_PATTERN = re.compile(r"^(.*?): (.*)$")
SENTINEL_START_PATTERN = re.compile(r"^= =: ([^:]{1,80}): ?(.*)$")
DOUBLE_START_PATTERN = re.compile(r"^([^:\n]{1,80}): ([^:\n]{1,80}): ?(.*)$")
LIST_PREFIX_PATTERN = re.compile(r"^[0-9一二三四五六七八九十]+[、.．)][^ ]*")

FIELD_NAME_EQUALS = {
    "甲方",
    "乙方",
    "收件人",
    "收货人",
    "手机号",
    "手机号码",
    "所在地区",
    "详细地址",
    "地址",
    "姓名",
    "身份证",
    "身份证号",
    "银行卡号",
    "开户行",
    "账号",
    "支行信息",
    "邮箱",
    "微信",
    "微信号",
    "电话",
    "联系电话",
    "联系人",
    "联系人姓名",
    "艺名",
    "合作金额",
    "抬头",
    "税号",
    "单位地址",
    "单位全称",
    "账户名称",
    "统一信用代码",
    "账户号码",
    "开户地址",
    "行号",
    "个人姓名",
    "联系人微信",
    "项目名称",
    "品牌产品*",
    "品牌产品",
    "合作时间*",
    "合作平台*",
    "合作账号",
    "合作需求",
    "合作形式*",
}
FIELD_NAME_HINTS = [
    "价格",
    "返点",
    "档期",
    "地址",
    "电话",
    "邮箱",
    "账号",
    "税号",
    "发票",
    "开户",
    "联系人",
    "机构刊例",
    "返点政策",
    "产品链接",
    "合作时间",
    "合作平台",
    "合作账号",
    "合作形式",
]
PLACEHOLDER_SPEAKERS = {"= =", "", "你", "你。"}


@dataclass
class TopMessage:
    source_name: str
    source_label: str
    top_index: int
    create_time: int
    formatted_time: str
    content: str
    lines: list[str]


@dataclass
class SegmentStart:
    line_index: int
    kind: str
    raw_line: str
    first_speaker: str | None = None
    hint_speaker: str | None = None
    seed_text: str | None = None


@dataclass
class ParsedMessage:
    speaker: str
    text: str
    line_start: int
    line_end: int


@dataclass
class Record:
    record_id: str
    source_name: str
    source_label: str
    source_top_message_index: int
    source_top_create_time: int
    source_top_formatted_time: str
    record_order: int
    pair_key: str
    participants: list[str]
    line_start: int
    line_end: int
    start_kind: str
    messages: list[ParsedMessage]
    output_relpath: str | None = None


@dataclass
class UnresolvedBlock:
    unresolved_id: str
    source_name: str
    source_label: str
    source_top_message_index: int
    source_top_create_time: int
    source_top_formatted_time: str
    record_order: int
    line_start: int
    line_end: int
    start_kind: str
    reason: str
    speakers_seen: list[str]
    raw_lines: list[str]


@dataclass
class ExtractionState:
    records: list[Record] = field(default_factory=list)
    unresolved: list[UnresolvedBlock] = field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="提取嵌套转发聊天中的最深层两人对话，并按同 pair 合并。")
    parser.add_argument(
        "--output-dir",
        type=str,
        default=str(OUTPUT_ROOT),
        help="输出目录，默认写入 contact_db/outputs/nested_forwarded_chat_extraction",
    )
    return parser.parse_args()


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def ensure_clean_output_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def normalize_visible(text: str) -> str:
    return re.sub(r"[\s\u2005\u3000]+", "", text).strip()


def normalize_pair_member(text: str) -> str:
    return normalize_visible(text).lower()


def format_ts(ts: int) -> str:
    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def parse_top_messages(config: dict) -> list[TopMessage]:
    data = load_json(config["path"])
    messages = data.get("messages", [])
    parsed: list[TopMessage] = []
    for idx, message in enumerate(messages):
        create_time = int(message.get("createTime") or 0)
        parsed.append(
            TopMessage(
                source_name=config["name"],
                source_label=config["label"],
                top_index=idx,
                create_time=create_time,
                formatted_time=format_ts(create_time),
                content=message.get("content") or "",
                lines=(message.get("content") or "").splitlines(),
            )
        )
    return parsed


def is_field_like_name(name: str) -> bool:
    stripped = name.strip()
    compact = normalize_visible(stripped)
    if not compact:
        return True
    if compact in FIELD_NAME_EQUALS:
        return True
    if LIST_PREFIX_PATTERN.match(stripped):
        return True
    if len(compact) <= 20 and any(hint in compact for hint in FIELD_NAME_HINTS):
        return True
    if compact.endswith(("号", "码")) and any(prefix in compact for prefix in ("身份", "银行", "订单", "支付")):
        return True
    if compact.startswith(("http", "https", "@", "【")):
        return True
    if "：" in stripped:
        return True
    return False


def looks_like_name_token(text: str) -> bool:
    compact = normalize_visible(text)
    if not compact:
        return False
    if len(compact) > 32:
        return False
    if compact in PLACEHOLDER_SPEAKERS:
        return False
    if is_field_like_name(compact):
        return False
    if compact.startswith(("http", "https", "@", "[", "【")):
        return False
    if any(token in compact for token in ("项目名称", "品牌产品", "合作时间", "合作平台", "合作需求", "产品链接")):
        return False
    return True


def safe_name(text: str) -> str:
    cleaned = text.replace("/", "／").replace("\\", "＼").replace(":", "：")
    cleaned = cleaned.replace("*", "＊").replace("?", "？").replace("\"", "＂")
    cleaned = cleaned.replace("<", "＜").replace(">", "＞").replace("|", "｜")
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned[:80] or "unknown"


def explicit_start_from_line(line: str, line_index: int) -> SegmentStart | None:
    sentinel_match = SENTINEL_START_PATTERN.match(line)
    if sentinel_match:
        first_speaker = sentinel_match.group(1).strip()
        if looks_like_name_token(first_speaker):
            return SegmentStart(
                line_index=line_index,
                kind="sentinel_start",
                raw_line=line,
                first_speaker=first_speaker,
                seed_text=sentinel_match.group(2),
            )

    double_match = DOUBLE_START_PATTERN.match(line)
    if double_match:
        outer_speaker = double_match.group(1).strip()
        first_speaker = double_match.group(2).strip()
        if (
            looks_like_name_token(first_speaker)
            and looks_like_name_token(outer_speaker)
            and not HEADER_PATTERN.match(line)
        ):
            return SegmentStart(
                line_index=line_index,
                kind="double_start",
                raw_line=line,
                first_speaker=first_speaker,
                hint_speaker=outer_speaker,
                seed_text=double_match.group(3),
            )

    return None


def looks_like_title_text(text: str) -> bool:
    compact = normalize_visible(text)
    if not compact or len(compact) > 30:
        return False
    if compact.startswith(("http", "@", "[", "【")):
        return False
    if any(token in compact for token in ("合作", "老师", "收到", "好的", "可以", "确认", "档期", "返点", "报价")):
        return False
    punctuation = "，。！？；：~（）()[]【】"
    punct_count = sum(1 for ch in compact if ch in punctuation)
    return punct_count <= 1


def next_speaker_line(lines: list[str], start_index: int) -> tuple[int, str, str] | None:
    for idx in range(start_index, len(lines)):
        match = SPEAKER_PATTERN.match(lines[idx])
        if match:
            return idx, match.group(1).strip(), match.group(2)
    return None


def has_continuation_lines(lines: list[str], line_index: int) -> bool:
    for idx in range(line_index + 1, min(line_index + 6, len(lines))):
        if not lines[idx].strip():
            continue
        if SPEAKER_PATTERN.match(lines[idx]):
            return False
        return True
    return False


def implicit_title_starts(lines: list[str]) -> list[SegmentStart]:
    starts: list[SegmentStart] = []
    for idx, line in enumerate(lines):
        match = SPEAKER_PATTERN.match(line)
        if not match:
            continue
        speaker = match.group(1).strip()
        text = match.group(2)
        if is_field_like_name(speaker) or not looks_like_title_text(text):
            continue
        next_item = next_different_speaker_line(lines, idx, speaker)
        if next_item is None:
            continue
        if not has_continuation_lines(lines, idx):
            continue
        starts.append(
            SegmentStart(
                line_index=idx,
                kind="title_start",
                raw_line=line,
                first_speaker=speaker,
                seed_text=text,
            )
        )
    return starts


def next_different_speaker_line(lines: list[str], start_index: int, current_speaker: str) -> tuple[int, str, str] | None:
    for idx in range(start_index + 1, len(lines)):
        match = SPEAKER_PATTERN.match(lines[idx])
        if not match:
            continue
        speaker = match.group(1).strip()
        if speaker == current_speaker:
            continue
        return idx, speaker, match.group(2)
    return None


def find_segment_starts(top_message: TopMessage) -> list[SegmentStart]:
    explicit_starts: list[SegmentStart] = []
    for idx, line in enumerate(top_message.lines):
        start = explicit_start_from_line(line, idx)
        if start:
            explicit_starts.append(start)
    if explicit_starts:
        return dedupe_starts(explicit_starts)
    return dedupe_starts(implicit_title_starts(top_message.lines))


def dedupe_starts(starts: list[SegmentStart]) -> list[SegmentStart]:
    deduped: list[SegmentStart] = []
    seen: set[int] = set()
    for start in starts:
        if start.line_index in seen:
            continue
        deduped.append(start)
        seen.add(start.line_index)
    deduped.sort(key=lambda item: item.line_index)
    return deduped


def iter_segments(top_message: TopMessage) -> Iterable[tuple[SegmentStart, int]]:
    starts = find_segment_starts(top_message)
    for idx, start in enumerate(starts):
        end_line = len(top_message.lines) - 1
        if idx + 1 < len(starts):
            end_line = starts[idx + 1].line_index - 1
        yield start, end_line


def resolved_speaker_from_start(start: SegmentStart) -> str | None:
    if start.kind in {"sentinel_start", "double_start", "title_start"}:
        return start.first_speaker
    return None


def maybe_map_placeholder_speaker(speaker: str, participants: list[str]) -> str:
    normalized = normalize_visible(speaker)
    if normalized == "= =" and participants:
        return participants[0]
    return speaker


def flush_message(messages: list[ParsedMessage], current: dict[str, object] | None) -> None:
    if not current:
        return
    text = str(current["text"]).rstrip()
    if not text:
        return
    messages.append(
        ParsedMessage(
            speaker=str(current["speaker"]),
            text=text,
            line_start=int(current["line_start"]),
            line_end=int(current["line_end"]),
        )
    )


def parse_segment(
    top_message: TopMessage,
    start: SegmentStart,
    end_line: int,
    global_record_index: int,
) -> Record | UnresolvedBlock:
    lines = top_message.lines
    participants: list[str] = []
    speakers_seen: list[str] = []
    messages: list[ParsedMessage] = []
    current: dict[str, object] | None = None
    unresolved_reason: str | None = None

    def register_speaker(name: str) -> None:
        nonlocal unresolved_reason
        if name not in speakers_seen:
            speakers_seen.append(name)
        if name not in participants:
            participants.append(name)
        if len(participants) > 2 and unresolved_reason is None:
            unresolved_reason = f"出现第三个真实说话人：{name}"

    def begin_message(speaker: str, text: str, line_index: int) -> None:
        nonlocal current
        flush_message(messages, current)
        current = {
            "speaker": speaker,
            "text": text,
            "line_start": line_index,
            "line_end": line_index,
        }

    first_speaker = resolved_speaker_from_start(start)
    if first_speaker:
        register_speaker(first_speaker)
        begin_message(first_speaker, start.seed_text or "", start.line_index)

    for line_index in range(start.line_index + 1, end_line + 1):
        line = lines[line_index]
        if HEADER_PATTERN.match(line):
            continue

        match = SPEAKER_PATTERN.match(line)
        if match:
            speaker = maybe_map_placeholder_speaker(match.group(1).strip(), participants)
            text = match.group(2)
            if is_field_like_name(speaker):
                if current is None:
                    current = {
                        "speaker": first_speaker or "__unknown__",
                        "text": line,
                        "line_start": line_index,
                        "line_end": line_index,
                    }
                else:
                    current["text"] = f"{current['text']}\n{line}"
                    current["line_end"] = line_index
                continue

            register_speaker(speaker)
            if unresolved_reason:
                if current is None:
                    current = {
                        "speaker": speaker,
                        "text": text,
                        "line_start": line_index,
                        "line_end": line_index,
                    }
                else:
                    current["text"] = f"{current['text']}\n{line}"
                    current["line_end"] = line_index
                continue

            begin_message(speaker, text, line_index)
            continue

        if current is None:
            current = {
                "speaker": first_speaker or "__unknown__",
                "text": line,
                "line_start": line_index,
                "line_end": line_index,
            }
        else:
            current["text"] = f"{current['text']}\n{line}" if current["text"] else line
            current["line_end"] = line_index

    flush_message(messages, current)

    if len(participants) < 2:
        unresolved_reason = unresolved_reason or "未能识别出两个真实说话人"

    if unresolved_reason:
        return UnresolvedBlock(
            unresolved_id=f"unresolved_{global_record_index:04d}",
            source_name=top_message.source_name,
            source_label=top_message.source_label,
            source_top_message_index=top_message.top_index,
            source_top_create_time=top_message.create_time,
            source_top_formatted_time=top_message.formatted_time,
            record_order=global_record_index,
            line_start=start.line_index,
            line_end=end_line,
            start_kind=start.kind,
            reason=unresolved_reason,
            speakers_seen=speakers_seen,
            raw_lines=lines[start.line_index : end_line + 1],
        )

    participants = participants[:2]
    pair_key = build_pair_key(participants[0], participants[1])
    return Record(
        record_id=f"record_{global_record_index:04d}",
        source_name=top_message.source_name,
        source_label=top_message.source_label,
        source_top_message_index=top_message.top_index,
        source_top_create_time=top_message.create_time,
        source_top_formatted_time=top_message.formatted_time,
        record_order=global_record_index,
        pair_key=pair_key,
        participants=participants,
        line_start=start.line_index,
        line_end=end_line,
        start_kind=start.kind,
        messages=messages,
    )


def build_pair_key(participant_a: str, participant_b: str) -> str:
    left = normalize_pair_member(participant_a)
    right = normalize_pair_member(participant_b)
    ordered = sorted([left, right])
    return "__".join(ordered)


def extract_records(top_messages: Iterable[TopMessage]) -> ExtractionState:
    state = ExtractionState()
    global_record_index = 1
    for top_message in top_messages:
        for start, end_line in iter_segments(top_message):
            parsed = parse_segment(top_message, start, end_line, global_record_index)
            if isinstance(parsed, Record):
                state.records.append(parsed)
            else:
                state.unresolved.append(parsed)
            global_record_index += 1
    return state


def speaker_username(name: str) -> str:
    compact = normalize_pair_member(name) or "unknown"
    safe = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "_", compact).strip("_")
    return f"participant_{safe or 'unknown'}"


def record_to_weflow_dict(record: Record, merged_order: int | None = None) -> dict:
    participant_a, participant_b = record.participants
    last_timestamp = record.source_top_create_time
    messages = []
    for idx, message in enumerate(record.messages, start=1):
        last_timestamp = record.source_top_create_time
        messages.append(
            {
                "localId": idx,
                "createTime": record.source_top_create_time,
                "formattedTime": record.source_top_formatted_time,
                "type": "文本消息",
                "localType": 1,
                "content": message.text,
                "isSend": 1 if message.speaker == participant_a else 0,
                "senderUsername": speaker_username(message.speaker),
                "senderDisplayName": message.speaker,
                "source": record.source_label,
                "platformMessageId": f"{record.record_id}_{idx:04d}",
                "sourceFile": record.source_label,
                "sourceTopMessageIndex": record.source_top_message_index,
                "sourceLineStart": message.line_start,
                "sourceLineEnd": message.line_end,
                "recordOrder": record.record_order,
                "mergedOrder": merged_order,
            }
        )

    return {
        "weflow": {
            "version": "1.0.3",
            "exportedAt": int(datetime.now().timestamp()),
            "generator": "extract_nested_forwarded_chats",
        },
        "session": {
            "wxid": record.record_id,
            "nickname": participant_b,
            "remark": "",
            "displayName": f"{participant_a} & {participant_b}",
            "participants": [participant_a, participant_b],
            "pairKey": record.pair_key,
            "type": "friend",
            "lastTimestamp": last_timestamp,
            "messageCount": len(messages),
            "avatar": "",
            "sourceFile": record.source_label,
            "sourceTopMessageIndex": record.source_top_message_index,
            "recordOrder": record.record_order,
            "lineRange": [record.line_start, record.line_end],
            "startKind": record.start_kind,
        },
        "messages": messages,
    }


def write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False))
            handle.write("\n")


def write_individual_records(records: list[Record], output_root: Path) -> None:
    base_dir = output_root / "individual_records"
    for record in records:
        pair_name = "__".join(safe_name(name) for name in record.participants)
        file_name = f"{record.record_order:04d}_{pair_name}.json"
        relpath = Path("individual_records") / record.source_name / file_name
        target = output_root / relpath
        target.parent.mkdir(parents=True, exist_ok=True)
        record.output_relpath = str(relpath)
        write_json(target, record_to_weflow_dict(record))


def merge_records(records: list[Record]) -> list[dict]:
    grouped: dict[str, list[Record]] = {}
    for record in records:
        grouped.setdefault(record.pair_key, []).append(record)

    merged_payloads: list[dict] = []
    merged_dir_entries: list[tuple[str, dict]] = []

    for pair_key, items in grouped.items():
        ordered_records = sorted(
            items,
            key=lambda item: (
                item.source_top_create_time,
                item.source_label,
                item.source_top_message_index,
                item.record_order,
            ),
        )
        participant_a, participant_b = ordered_records[0].participants
        merged_messages = []
        merged_order = 1
        for record in ordered_records:
            payload = record_to_weflow_dict(record, merged_order=merged_order)
            for message in payload["messages"]:
                message["localId"] = len(merged_messages) + 1
                merged_messages.append(message)
            merged_order += 1

        merged_payload = {
            "weflow": {
                "version": "1.0.3",
                "exportedAt": int(datetime.now().timestamp()),
                "generator": "extract_nested_forwarded_chats",
            },
            "session": {
                "wxid": f"merged_{pair_key}",
                "nickname": participant_b,
                "remark": "",
                "displayName": f"{participant_a} & {participant_b}",
                "participants": [participant_a, participant_b],
                "pairKey": pair_key,
                "type": "friend",
                "lastTimestamp": ordered_records[-1].source_top_create_time,
                "messageCount": len(merged_messages),
                "avatar": "",
                "sourceFiles": sorted({record.source_label for record in ordered_records}),
                "recordCount": len(ordered_records),
            },
            "messages": merged_messages,
        }

        file_name = f"{safe_name(participant_a)}__{safe_name(participant_b)}.json"
        merged_dir_entries.append((file_name, merged_payload))
        merged_payloads.append(
            {
                "pairKey": pair_key,
                "participants": [participant_a, participant_b],
                "recordCount": len(ordered_records),
                "messageCount": len(merged_messages),
                "sourceFiles": sorted({record.source_label for record in ordered_records}),
                "recordIds": [record.record_id for record in ordered_records],
                "fileName": file_name,
            }
        )

    return merged_payloads, merged_dir_entries


def write_merged_records(records: list[Record], output_root: Path) -> list[dict]:
    merged_manifest_rows, merged_entries = merge_records(records)
    merged_dir = output_root / "merged_by_pair"
    merged_dir.mkdir(parents=True, exist_ok=True)
    for file_name, payload in merged_entries:
        write_json(merged_dir / file_name, payload)
    return merged_manifest_rows


def build_individual_manifest(records: list[Record]) -> list[dict]:
    rows = []
    for record in records:
        rows.append(
            {
                "recordId": record.record_id,
                "sourceName": record.source_name,
                "sourceFile": record.source_label,
                "sourceTopMessageIndex": record.source_top_message_index,
                "sourceTopCreateTime": record.source_top_create_time,
                "sourceTopFormattedTime": record.source_top_formatted_time,
                "recordOrder": record.record_order,
                "pairKey": record.pair_key,
                "participants": record.participants,
                "messageCount": len(record.messages),
                "lineRange": [record.line_start, record.line_end],
                "startKind": record.start_kind,
                "outputFile": record.output_relpath,
            }
        )
    return rows


def build_unresolved_manifest(unresolved: list[UnresolvedBlock]) -> list[dict]:
    rows = []
    for block in unresolved:
        rows.append(
            {
                "unresolvedId": block.unresolved_id,
                "sourceName": block.source_name,
                "sourceFile": block.source_label,
                "sourceTopMessageIndex": block.source_top_message_index,
                "sourceTopCreateTime": block.source_top_create_time,
                "sourceTopFormattedTime": block.source_top_formatted_time,
                "recordOrder": block.record_order,
                "lineRange": [block.line_start, block.line_end],
                "startKind": block.start_kind,
                "reason": block.reason,
                "speakersSeen": block.speakers_seen,
                "rawLines": block.raw_lines,
            }
        )
    return rows


def build_summary_markdown(
    records: list[Record],
    unresolved: list[UnresolvedBlock],
    merged_manifest: list[dict],
) -> str:
    per_source_resolved = {config["name"]: 0 for config in SOURCE_CONFIGS}
    per_source_unresolved = {config["name"]: 0 for config in SOURCE_CONFIGS}
    for record in records:
        per_source_resolved[record.source_name] += 1
    for block in unresolved:
        per_source_unresolved[block.source_name] += 1

    duplicate_pair_count = sum(1 for row in merged_manifest if row["recordCount"] > 1)
    total_expected = sum(config["expected_count"] for config in SOURCE_CONFIGS)
    total_resolved = len(records)
    total_unresolved = len(unresolved)
    actual_total_segments = total_resolved + total_unresolved

    lines = [
        "# 嵌套转发聊天提取摘要",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 已提取单条两人聊天文件：{total_resolved}",
        f"- 已合并 pair 文件：{len(merged_manifest)}",
        f"- 重复 pair 数量：{duplicate_pair_count}",
        f"- unresolved 数量：{total_unresolved}",
        f"- 用户预估总量：{total_expected}（Tony 78 + 文件传输助手 13）",
        f"- 实际识别出的分段总量：{actual_total_segments}",
        f"- 与用户预估差异：{actual_total_segments - total_expected:+d}",
        "",
        "## 分源统计",
        "",
        "| 源文件 | 用户预估 | 成功提取 | unresolved | 分段总量 | 与预估差异 |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]

    for config in SOURCE_CONFIGS:
        resolved_count = per_source_resolved[config["name"]]
        unresolved_count = per_source_unresolved[config["name"]]
        segment_total = resolved_count + unresolved_count
        diff = segment_total - config["expected_count"]
        lines.append(
            f"| {config['label']} | {config['expected_count']} | {resolved_count} | {unresolved_count} | {segment_total} | {diff:+d} |"
        )

    lines.extend(
        [
            "",
            "## 说明",
            "",
            "- `成功提取` 只统计被安全识别为最深层两人对话的块。",
            "- `unresolved` 表示块中出现第三个真实说话人，或无法稳定识别出两位说话人，因此保留原始块而不强拆。",
            "- 合并规则按同一对微信名进行，pair key 使用双方微信名最小归一化后的无序组合。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> None:
    args = parse_args()
    output_root = Path(args.output_dir).resolve()
    ensure_clean_output_dir(output_root)

    top_messages: list[TopMessage] = []
    for config in SOURCE_CONFIGS:
        top_messages.extend(parse_top_messages(config))

    state = extract_records(top_messages)
    state.records.sort(
        key=lambda item: (
            item.source_top_create_time,
            item.source_label,
            item.source_top_message_index,
            item.record_order,
        )
    )
    state.unresolved.sort(
        key=lambda item: (
            item.source_top_create_time,
            item.source_label,
            item.source_top_message_index,
            item.record_order,
        )
    )

    write_individual_records(state.records, output_root)
    merged_manifest = write_merged_records(state.records, output_root)

    manifests_dir = output_root / "manifests"
    manifests_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(manifests_dir / "individual_records.jsonl", build_individual_manifest(state.records))
    write_jsonl(manifests_dir / "merged_records.jsonl", merged_manifest)

    unresolved_dir = output_root / "unresolved"
    unresolved_dir.mkdir(parents=True, exist_ok=True)
    write_jsonl(unresolved_dir / "unresolved_blocks.jsonl", build_unresolved_manifest(state.unresolved))

    reports_dir = output_root / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    summary = build_summary_markdown(state.records, state.unresolved, merged_manifest)
    (reports_dir / "extraction_summary.md").write_text(summary, encoding="utf-8")

    print(summary)
    print(f"输出目录: {output_root}")


if __name__ == "__main__":
    main()
