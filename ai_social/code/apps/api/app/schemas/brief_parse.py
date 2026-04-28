from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.schemas.shortlist import ShortlistRequirement


class BriefParseSourceType(str, Enum):
    MANUAL_TEXT = "manual_text"
    MEETING_NOTES = "meeting_notes"
    CHAT_TRANSCRIPT = "chat_transcript"
    FORM_INPUT = "form_input"
    UNKNOWN = "unknown"


class BriefParseSourceLanguage(str, Enum):
    ZH = "zh"
    EN = "en"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class BriefParseStatus(str, Enum):
    COMPLETE = "complete"
    PARTIAL = "partial"
    NEEDS_REVIEW = "needs_review"


class BriefPriorityColor(str, Enum):
    RED = "red"
    GREEN = "green"
    YELLOW = "yellow"


class BriefConstraintBucketName(str, Enum):
    HARD = "hard_constraints"
    PREFERRED = "preferred_constraints"
    NEGOTIABLE = "negotiable_constraints"


class BriefParseIssueCode(str, Enum):
    MISSING_FIELD = "missing_field"
    AMBIGUOUS_FIELD = "ambiguous_field"
    CONTRADICTORY_FIELD = "contradictory_field"
    UNSUPPORTED_REQUIREMENT = "unsupported_requirement"


class BriefParseIssueSeverity(str, Enum):
    WARNING = "warning"
    ERROR = "error"


class BriefParseMetadata(BaseModel):
    """Optional request metadata for tracing how the brief entered the parser."""

    model_config = ConfigDict(extra="forbid")

    brief_id: str | None = Field(default=None, description="Optional caller-provided identifier for the brief.")
    source_type: BriefParseSourceType = Field(
        default=BriefParseSourceType.UNKNOWN,
        description="Where the raw brief text originated.",
    )
    source_language: BriefParseSourceLanguage = Field(
        default=BriefParseSourceLanguage.UNKNOWN,
        description="Primary language of the source brief.",
    )
    dry_run: bool = Field(
        default=True,
        description="Safety switch. The contract currently supports dry_run=true only.",
    )


class BriefParseInput(BaseModel):
    """Backend-facing request contract for brief parsing."""

    model_config = ConfigDict(extra="forbid")

    raw_text: str | None = Field(
        default=None,
        description="Raw client brief, notes, or pasted requirements to parse.",
    )
    structured_requirement: ShortlistRequirement | None = Field(
        default=None,
        description="Optional already-structured requirement used for validation-only flows.",
    )
    metadata: BriefParseMetadata = Field(
        default_factory=BriefParseMetadata,
        description="Optional request metadata. dry_run must remain true in this repo.",
    )

    @model_validator(mode="after")
    def validate_single_input(self) -> "BriefParseInput":
        has_raw = bool(self.raw_text and self.raw_text.strip())
        has_structured = self.structured_requirement is not None
        if has_raw == has_structured:
            raise ValueError("Provide exactly one of raw_text or structured_requirement.")
        if not self.metadata.dry_run:
            raise ValueError("brief-parse currently supports dry_run=true only.")
        return self


class BriefParseIssue(BaseModel):
    """Normalized diagnostic item surfaced by the brief parser."""

    model_config = ConfigDict(extra="forbid")

    code: BriefParseIssueCode
    severity: BriefParseIssueSeverity
    field: str = Field(description="Field or domain area impacted by this issue.")
    message: str = Field(description="Human-readable explanation for engineers and reviewers.")
    source_text: str | None = Field(
        default=None,
        description="Source snippet or normalized value that triggered the issue, when available.",
    )


class BriefPrioritySignal(BaseModel):
    """Priority mapping item derived from the brief and mapped into repo constraint buckets."""

    model_config = ConfigDict(extra="forbid")

    field: str = Field(description="Requirement field or bucket path represented by the signal.")
    value: str = Field(description="Normalized value or note carried downstream.")
    priority_color: BriefPriorityColor
    mapped_bucket: BriefConstraintBucketName
    rationale: str = Field(description="Why the signal was mapped to this priority bucket.")
    source_text: str | None = Field(
        default=None,
        description="Original brief line or phrase when the mapping came from explicit text.",
    )


class BriefParseOutput(BaseModel):
    """Backend-facing response contract for brief parsing."""

    model_config = ConfigDict(extra="forbid")

    structured_requirement: ShortlistRequirement
    parse_status: BriefParseStatus
    parser_notes: list[str] = Field(default_factory=list)
    priority_signals: list[BriefPrioritySignal] = Field(default_factory=list)
    missing_information: list[BriefParseIssue] = Field(default_factory=list)
    ambiguities: list[BriefParseIssue] = Field(default_factory=list)
    contradictions: list[BriefParseIssue] = Field(default_factory=list)
    unsupported_requirements: list[BriefParseIssue] = Field(default_factory=list)
    defaults_applied: list[str] = Field(default_factory=list)
