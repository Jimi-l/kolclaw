from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class Mp4LinkRecord(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    record_id: str
    workflow_run_id: str | None = None
    video_url: str
    creator_name: str | None = None
    status: Literal["pending", "processing", "success", "failed"]
    direct_mp4_url: str | None = None
    source: str | None = None
    access_mode: Literal["external_direct", "browser_context_only", "failed"] | None = None
    final_url: str | None = None
    content_type: str | None = None
    content_length: str | None = None
    probe_status_code: int | None = None
    probe_content_range: str | None = None
    attempt_count: int = 0
    last_error: str | None = None
    updated_at: str
