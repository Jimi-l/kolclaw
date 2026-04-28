from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class ExternalDocReference(BaseModel):
    doc_id: str
    title: str
    category: Literal["operational", "strategy", "archive"]
    relative_path: str
    absolute_path: str
    source_type: str
    used_in_v1: bool = False
    usage_notes: list[str] = Field(default_factory=list)


class ExternalDocReferenceResponse(BaseModel):
    references: list[ExternalDocReference] = Field(default_factory=list)
