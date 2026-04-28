from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable


URL_PATTERN = re.compile(r"https?://[^\s]+")
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
PHONE_PATTERN = re.compile(r"\b1[3-9]\d{9}\b")
BANK_ACCOUNT_PATTERN = re.compile(r"\b\d{16,19}\b")
IDCARD_PATTERN = re.compile(r"\b\d{17}[\dXx]\b")
MULTI_SPACE_PATTERN = re.compile(r"[ \t]+")


def short_hash(text: str, length: int = 10) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:length]


def list_json_files(input_dir: str | Path) -> list[Path]:
    path = Path(input_dir)
    if not path.exists():
        return []
    return sorted(p for p in path.iterdir() if p.is_file() and p.suffix.lower() == ".json")


def load_json(file_path: str | Path) -> dict[str, Any]:
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def ensure_dir(path: str | Path) -> Path:
    output = Path(path)
    output.mkdir(parents=True, exist_ok=True)
    return output


def write_jsonl(file_path: str | Path, items: Iterable[dict[str, Any]]) -> None:
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with file_path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False))
            f.write("\n")


def write_text(file_path: str | Path, content: str) -> None:
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    file_path.write_text(content, encoding="utf-8")


def normalize_text(text: str | None) -> str:
    if text is None:
        return ""

    lines = []
    for raw_line in str(text).splitlines():
        line = MULTI_SPACE_PATTERN.sub(" ", raw_line).strip()
        if line:
            lines.append(line)
    return "\n".join(lines).strip()


def mask_sensitive_content(text: str | None) -> str:
    normalized = normalize_text(text)
    normalized = URL_PATTERN.sub("[URL]", normalized)
    normalized = EMAIL_PATTERN.sub("[EMAIL]", normalized)
    normalized = PHONE_PATTERN.sub("[PHONE]", normalized)
    normalized = BANK_ACCOUNT_PATTERN.sub("[BANK_ACCOUNT]", normalized)
    normalized = IDCARD_PATTERN.sub("[IDCARD]", normalized)
    return normalized


def dedupe_keep_order(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = value.strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def dump_yaml(data: Any, indent: int = 0) -> str:
    prefix = " " * indent
    if isinstance(data, dict):
        lines: list[str] = []
        for key, value in data.items():
            if isinstance(value, (dict, list)):
                lines.append(f"{prefix}{key}:")
                lines.append(dump_yaml(value, indent + 2))
            else:
                lines.append(f"{prefix}{key}: {format_yaml_scalar(value)}")
        return "\n".join(lines)
    if isinstance(data, list):
        lines = []
        for item in data:
            if isinstance(item, (dict, list)):
                lines.append(f"{prefix}-")
                lines.append(dump_yaml(item, indent + 2))
            else:
                lines.append(f"{prefix}- {format_yaml_scalar(item)}")
        return "\n".join(lines)
    return f"{prefix}{format_yaml_scalar(data)}"


def format_yaml_scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    text = str(value).replace('"', '\\"')
    return f'"{text}"'
