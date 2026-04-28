
from __future__ import annotations

from typing import Dict, List, Tuple


class ValidationError:
    def __init__(self, field: str, message: str, severity: str = "error"):
        self.field = field
        self.message = message
        self.severity = severity  # "error" or "warning"

    def __str__(self) -> str:
        return f"[{self.severity.upper()}] {self.field}: {self.message}"


class WeFlowValidator:
    def __init__(self):
        pass

    def validate_file(self, raw_data: dict, filename: str) -> Tuple[bool, List[ValidationError]]:
        errors: List[ValidationError] = []

        if not isinstance(raw_data, dict):
            errors.append(ValidationError("root", "Root must be a dict"))
            return False, errors

        if "session" not in raw_data:
            errors.append(ValidationError("session", "Missing required field"))
        else:
            self._validate_session(raw_data["session"], errors)

        if "messages" not in raw_data:
            errors.append(ValidationError("messages", "Missing required field"))
        elif not isinstance(raw_data["messages"], list):
            errors.append(ValidationError("messages", "Must be a list"))
        else:
            for idx, msg in enumerate(raw_data["messages"]):
                self._validate_message(msg, idx, errors)

        has_errors = any(e.severity == "error" for e in errors)
        return not has_errors, errors

    def _validate_session(self, session: dict, errors: List[ValidationError]):
        if not isinstance(session, dict):
            errors.append(ValidationError("session", "Must be a dict"))
            return

        required_fields = ["wxid", "displayName", "type", "messageCount"]
        for field in required_fields:
            if field not in session:
                errors.append(ValidationError(f"session.{field}", "Missing required field"))

        if "messageCount" in session:
            mc = session["messageCount"]
            if not isinstance(mc, int) or mc < 0:
                errors.append(ValidationError("session.messageCount", "Must be a non-negative integer"))

    def _validate_message(self, msg: dict, idx: int, errors: List[ValidationError]):
        prefix = f"messages[{idx}]"

        if not isinstance(msg, dict):
            errors.append(ValidationError(prefix, "Must be a dict"))
            return

        required_fields = [
            "localId",
            "createTime",
            "type",
            "isSend",
            "senderUsername",
        ]
        for field in required_fields:
            if field not in msg:
                errors.append(ValidationError(f"{prefix}.{field}", "Missing required field"))

        if "isSend" in msg:
            is_send = msg["isSend"]
            if not isinstance(is_send, int) or is_send not in (0, 1):
                errors.append(ValidationError(
                    f"{prefix}.isSend",
                    f"Must be 0 or 1, got {is_send}",
                    severity="warning"
                ))

        if "type" in msg:
            msg_type = msg["type"]
            if not isinstance(msg_type, str):
                errors.append(ValidationError(f"{prefix}.type", "Must be a string"))
            elif msg_type not in ("文本消息", "图片消息", "语音消息", "视频消息", "文件消息"):
                errors.append(ValidationError(
                    f"{prefix}.type",
                    f"Unknown message type: {msg_type}",
                    severity="warning"
                ))

        if "content" in msg:
            content = msg["content"]
            msg_type = msg.get("type", "")
            if msg_type == "文本消息" and content is not None and not isinstance(content, str):
                errors.append(ValidationError(
                    f"{prefix}.content",
                    "Text message content must be a string",
                    severity="warning"
                ))


def format_validation_errors(errors: List[ValidationError]) -> List[str]:
    return [str(e) for e in errors]

