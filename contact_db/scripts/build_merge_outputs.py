#!/usr/bin/env python3
from __future__ import annotations

import json
import re
import shutil
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
INPUT_ROOT = PROJECT_ROOT / "outputs" / "nested_forwarded_chat_extraction"
OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "merge"

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
    "个人姓名",
    "身份证",
    "身份证号",
    "银行卡号",
    "开户行",
    "账号",
    "支行信息",
    "邮箱",
    "微信",
    "微信号",
    "联系人微信",
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


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def normalize_visible(text: str) -> str:
    return re.sub(r"[\s\u2005\u3000]+", "", text).strip()


def normalize_name(text: str) -> str:
    return normalize_visible(text).lower()


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


def speaker_username(name: str) -> str:
    compact = normalize_name(name) or "unknown"
    safe = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "_", compact).strip("_")
    return f"participant_{safe or 'unknown'}"


def parse_raw_lines_to_messages(raw_lines: list[str], default_speaker: str | None = None) -> list[dict]:
    messages: list[dict] = []
    current: dict | None = None

    def flush() -> None:
        nonlocal current
        if current and str(current["content"]).strip():
            messages.append(current)
        current = None

    for offset, line in enumerate(raw_lines):
        if HEADER_PATTERN.match(line):
            continue

        parsed_speaker: str | None = None
        parsed_text: str | None = None

        sentinel = SENTINEL_START_PATTERN.match(line)
        double = DOUBLE_START_PATTERN.match(line)
        plain = SPEAKER_PATTERN.match(line)

        if sentinel and looks_like_name_token(sentinel.group(1).strip()):
            parsed_speaker = sentinel.group(1).strip()
            parsed_text = sentinel.group(2)
        elif double and looks_like_name_token(double.group(2).strip()):
            parsed_speaker = double.group(2).strip()
            parsed_text = double.group(3)
        elif plain:
            candidate = plain.group(1).strip()
            if not is_field_like_name(candidate):
                parsed_speaker = candidate
                parsed_text = plain.group(2)

        if parsed_speaker is not None:
            flush()
            current = {
                "speaker": parsed_speaker,
                "content": parsed_text or "",
            }
            continue

        if current is None:
            current = {
                "speaker": default_speaker or "未识别说话人",
                "content": line,
            }
        else:
            if current["content"]:
                current["content"] = f"{current['content']}\n{line}"
            else:
                current["content"] = line

    flush()
    return messages


def ensure_clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def build_pair_key(participants: list[str]) -> str:
    ordered = sorted(normalize_name(item) for item in participants)
    return "__".join(ordered)


def choose_pair_order(participants: list[str], frequency: Counter[str]) -> list[str]:
    indexed = {name: idx for idx, name in enumerate(participants)}
    return sorted(
        participants,
        key=lambda name: (-frequency[normalize_name(name)], indexed[name], normalize_name(name)),
    )


def load_individual_records() -> list[dict]:
    manifests = load_jsonl(INPUT_ROOT / "manifests" / "individual_records.jsonl")
    records: list[dict] = []
    for row in manifests:
        payload = json.loads((INPUT_ROOT / row["outputFile"]).read_text(encoding="utf-8"))
        records.append(
            {
                "recordId": row["recordId"],
                "sourceName": row["sourceName"],
                "sourceFile": row["sourceFile"],
                "sourceTopMessageIndex": row["sourceTopMessageIndex"],
                "sourceTopCreateTime": row["sourceTopCreateTime"],
                "sourceTopFormattedTime": row["sourceTopFormattedTime"],
                "recordOrder": row["recordOrder"],
                "participants": row["participants"],
                "pairKey": row["pairKey"],
                "lineRange": row["lineRange"],
                "messages": payload["messages"],
            }
        )
    return records


def attach_single_speaker_blocks(records: list[dict], unresolved: list[dict]) -> tuple[list[dict], list[dict], int]:
    by_source: dict[str, list[dict]] = defaultdict(list)
    for record in records:
        by_source[record["sourceName"]].append(record)
    for source_records in by_source.values():
        source_records.sort(key=lambda item: (item["sourceTopMessageIndex"], item["lineRange"][0], item["recordOrder"]))

    remaining: list[dict] = []
    attached_count = 0

    for block in unresolved:
        speakers = [speaker for speaker in block["speakersSeen"] if speaker not in PLACEHOLDER_SPEAKERS]
        if len(speakers) != 1:
            remaining.append(block)
            continue

        speaker = speakers[0]
        target = None
        attach_mode = None
        source_records = by_source[block["sourceName"]]

        for record in source_records:
            if record["sourceTopMessageIndex"] != block["sourceTopMessageIndex"]:
                continue
            if record["lineRange"][0] > block["lineRange"][1] and speaker in record["participants"]:
                target = record
                attach_mode = "prepend"
                break

        if target is None:
            for record in reversed(source_records):
                if record["sourceTopMessageIndex"] != block["sourceTopMessageIndex"]:
                    continue
                if record["lineRange"][1] < block["lineRange"][0] and speaker in record["participants"]:
                    target = record
                    attach_mode = "append"
                    break

        if target is None:
            remaining.append(block)
            continue

        fragment_messages = parse_raw_lines_to_messages(block["rawLines"], default_speaker=speaker)
        converted = []
        for idx, message in enumerate(fragment_messages, start=1):
            converted.append(
                {
                    "localId": idx,
                    "createTime": block["sourceTopCreateTime"],
                    "formattedTime": block["sourceTopFormattedTime"],
                    "type": "文本消息",
                    "localType": 1,
                    "content": message["content"],
                    "senderUsername": speaker_username(message["speaker"]),
                    "senderDisplayName": message["speaker"],
                    "platformMessageId": f"{block['unresolvedId']}_{idx:04d}",
                    "sourceTopMessageIndex": block["sourceTopMessageIndex"],
                    "sourceLineStart": block["lineRange"][0],
                    "sourceLineEnd": block["lineRange"][1],
                    "recordOrder": block["recordOrder"],
                }
            )

        if attach_mode == "prepend":
            target["messages"] = converted + target["messages"]
            target["lineRange"][0] = min(target["lineRange"][0], block["lineRange"][0])
        else:
            target["messages"].extend(converted)
            target["lineRange"][1] = max(target["lineRange"][1], block["lineRange"][1])

        attached_count += 1

    return records, remaining, attached_count


def build_pair_outputs(records: list[dict]) -> tuple[list[tuple[str, dict]], int]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    participant_frequency = Counter()
    for record in records:
        grouped[record["pairKey"]].append(record)
        for participant in set(record["participants"]):
            participant_frequency[normalize_name(participant)] += 1

    outputs: list[tuple[str, dict]] = []
    for pair_key, items in grouped.items():
        items.sort(key=lambda item: (item["sourceTopCreateTime"], item["sourceTopMessageIndex"], item["recordOrder"]))
        participants = choose_pair_order(items[0]["participants"], participant_frequency)
        messages = []
        for record in items:
            for message in record["messages"]:
                messages.append(
                    {
                        "localId": len(messages) + 1,
                        "createTime": message["createTime"],
                        "formattedTime": message["formattedTime"],
                        "type": message["type"],
                        "localType": message["localType"],
                        "content": message["content"],
                        "isSend": 1 if message["senderDisplayName"] == participants[0] else 0,
                        "senderUsername": message["senderUsername"],
                        "senderDisplayName": message["senderDisplayName"],
                        "platformMessageId": message["platformMessageId"],
                        "sourceTopMessageIndex": message.get("sourceTopMessageIndex"),
                        "sourceLineStart": message.get("sourceLineStart"),
                        "sourceLineEnd": message.get("sourceLineEnd"),
                        "recordOrder": message.get("recordOrder"),
                    }
                )

        payload = {
            "weflow": {
                "version": "1.0.3",
                "exportedAt": int(datetime.now().timestamp()),
                "generator": "build_merge_outputs",
            },
            "session": {
                "wxid": f"merged_{pair_key}",
                "nickname": participants[-1],
                "remark": "",
                "displayName": " & ".join(participants),
                "participants": participants,
                "pairKey": pair_key,
                "type": "friend",
                "lastTimestamp": messages[-1]["createTime"] if messages else 0,
                "messageCount": len(messages),
                "avatar": "",
                "recordCount": len(items),
            },
            "messages": messages,
        }
        file_name = "__".join(safe_name(name) for name in participants) + ".json"
        outputs.append((file_name, payload))
    return outputs, len(grouped)


def group_filename_from_speakers(speakers: list[str], index: int) -> str:
    shown = speakers[:4]
    base = "__".join(safe_name(name) for name in shown)
    if len(speakers) > 4:
        base = f"{base}__等{len(speakers)}人"
    return f"群聊__{index:03d}__{base}.json"


def build_group_outputs(unresolved: list[dict]) -> list[tuple[str, dict]]:
    outputs: list[tuple[str, dict]] = []
    for idx, block in enumerate(unresolved, start=1):
        messages = parse_raw_lines_to_messages(block["rawLines"])
        participants: list[str] = []
        for message in messages:
            speaker = message["speaker"]
            if speaker in PLACEHOLDER_SPEAKERS or is_field_like_name(speaker):
                continue
            if speaker not in participants:
                participants.append(speaker)

        if len(participants) < 2:
            continue

        payload_messages = []
        for message in messages:
            speaker = message["speaker"]
            if speaker in PLACEHOLDER_SPEAKERS or is_field_like_name(speaker):
                continue
            payload_messages.append(
                {
                    "localId": len(payload_messages) + 1,
                    "createTime": block["sourceTopCreateTime"],
                    "formattedTime": block["sourceTopFormattedTime"],
                    "type": "文本消息",
                    "localType": 1,
                    "content": message["content"],
                    "isSend": 1 if speaker == participants[0] else 0,
                    "senderUsername": speaker_username(speaker),
                    "senderDisplayName": speaker,
                    "platformMessageId": f"{block['unresolvedId']}_{len(payload_messages)+1:04d}",
                    "sourceTopMessageIndex": block["sourceTopMessageIndex"],
                    "sourceLineStart": block["lineRange"][0],
                    "sourceLineEnd": block["lineRange"][1],
                    "recordOrder": block["recordOrder"],
                }
            )

        payload = {
            "weflow": {
                "version": "1.0.3",
                "exportedAt": int(datetime.now().timestamp()),
                "generator": "build_merge_outputs",
            },
            "session": {
                "wxid": block["unresolvedId"],
                "nickname": "群聊",
                "remark": "",
                "displayName": " / ".join(participants),
                "participants": participants,
                "pairKey": None,
                "type": "group",
                "lastTimestamp": block["sourceTopCreateTime"],
                "messageCount": len(payload_messages),
                "avatar": "",
                "groupReason": block["reason"],
            },
            "messages": payload_messages,
        }
        outputs.append((group_filename_from_speakers(participants, idx), payload))
    return outputs


def minify_payload(payload: dict) -> list[dict]:
    minimized: list[dict] = []
    for message in payload["messages"]:
        minimized.append(
            {
                "localId": message["localId"],
                "type": message["type"],
                "content": message["content"],
                "senderDisplayName": message["senderDisplayName"],
            }
        )
    return minimized


def write_payload(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(minify_payload(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def write_summary(
    output_dir: Path,
    pair_outputs: list[tuple[str, dict]],
    group_outputs: list[tuple[str, dict]],
    attached_count: int,
    unresolved_total: int,
) -> None:
    lines = [
        "# Merge 输出摘要",
        "",
        f"- 生成时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 二人聊天合并文件：{len(pair_outputs)}",
        f"- 群聊文件：{len(group_outputs)}",
        f"- 并回相邻聊天的单人残块：{attached_count}",
        f"- 原 unresolved 总数：{unresolved_total}",
        "",
        "## 说明",
        "",
        "- 本目录只保留最终对外文件，统一放在 `outputs/merge` 下。",
        "- 两个源文件统一按同一套规则处理，结果中不体现来源差异。",
        "- 每个 JSON 文件只保留消息数组，且每条消息只含 `localId / type / content / senderDisplayName`。",
        "- 多说话人 unresolved 已按群聊文件输出，文件名使用群聊中的几个微信名。",
    ]
    (output_dir / "merge_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    ensure_clean_dir(OUTPUT_ROOT)

    records = load_individual_records()
    unresolved = load_jsonl(INPUT_ROOT / "unresolved" / "unresolved_blocks.jsonl")
    unresolved_total = len(unresolved)

    records, unresolved, attached_count = attach_single_speaker_blocks(records, unresolved)
    pair_outputs, _ = build_pair_outputs(records)
    group_outputs = build_group_outputs(unresolved)

    for file_name, payload in pair_outputs:
        write_payload(OUTPUT_ROOT / file_name, payload)
    for file_name, payload in group_outputs:
        write_payload(OUTPUT_ROOT / file_name, payload)

    write_summary(OUTPUT_ROOT, pair_outputs, group_outputs, attached_count, unresolved_total)

    print(f'pair files: {len(pair_outputs)}')
    print(f'group files: {len(group_outputs)}')
    print(f'attached single-speaker fragments: {attached_count}')
    print(f'output: {OUTPUT_ROOT}')


if __name__ == "__main__":
    main()
