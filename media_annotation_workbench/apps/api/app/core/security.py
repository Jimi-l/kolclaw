from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from typing import Any


def hash_password(password: str, *, salt: str | None = None) -> str:
    salt_value = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_value.encode("utf-8"), 100_000)
    return f"{salt_value}${digest.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        salt, digest = stored_hash.split("$", 1)
    except ValueError:
        return False
    expected = hash_password(password, salt=salt)
    return hmac.compare_digest(expected, stored_hash)


def _b64_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64_decode(data: str) -> bytes:
    padded = data + "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8"))


def create_access_token(payload: dict[str, Any], secret_key: str, ttl_seconds: int) -> str:
    body = dict(payload)
    body["exp"] = int(time.time()) + ttl_seconds
    token_body = _b64_encode(json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
    signature = hmac.new(secret_key.encode("utf-8"), token_body.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{token_body}.{signature}"


def decode_access_token(token: str, secret_key: str) -> dict[str, Any]:
    try:
        token_body, signature = token.split(".", 1)
    except ValueError as exc:
        raise ValueError("Malformed token.") from exc

    expected_signature = hmac.new(secret_key.encode("utf-8"), token_body.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected_signature):
        raise ValueError("Invalid token signature.")

    payload = json.loads(_b64_decode(token_body).decode("utf-8"))
    if int(payload.get("exp", 0)) < int(time.time()):
        raise ValueError("Token expired.")
    return payload
