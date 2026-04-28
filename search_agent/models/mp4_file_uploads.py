from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


class Mp4FileUploadRecord(BaseModel):
    model_config = ConfigDict(use_enum_values=True)

    record_id: str
    workflow_run_id: str | None = None
    video_url: str
    creator_name: str | None = None
    status: Literal["pending", "downloading", "uploading", "success", "failed"]
    direct_mp4_url: str | None = None
    final_url: str | None = None
    source_mp4_access_mode: str | None = None
    file_id: str | None = None
    file_purpose: str | None = None
    filename: str | None = None
    content_type: str | None = None
    content_length: str | None = None
    downloaded_bytes: int | None = None
    sha256: str | None = None
    attempt_count: int = 0
    last_error: str | None = None
    updated_at: str
