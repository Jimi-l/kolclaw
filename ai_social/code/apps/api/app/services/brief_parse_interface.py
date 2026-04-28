from __future__ import annotations

import re

from app.schemas.brief_parse import (
    BriefConstraintBucketName,
    BriefParseInput,
    BriefParseIssue,
    BriefParseIssueCode,
    BriefParseIssueSeverity,
    BriefParseOutput,
    BriefParseStatus,
    BriefPriorityColor,
    BriefPrioritySignal,
)
from app.schemas.shortlist import ShortlistRequirement
from app.services.shortlist_brief_parser import CATEGORY_SIGNALS, structure_shortlist_requirement
from app.utils.normalization import unique_list

UNSUPPORTED_PLATFORM_SIGNALS = {
    "xiaohongshu": "Current V1 shortlist flow supports Douyin/Xingtu only.",
    "小红书": "Current V1 shortlist flow supports Douyin/Xingtu only.",
    "xhs": "Current V1 shortlist flow supports Douyin/Xingtu only.",
    "bilibili": "Current V1 shortlist flow supports Douyin/Xingtu only.",
    "微博": "Current V1 shortlist flow supports Douyin/Xingtu only.",
    "weibo": "Current V1 shortlist flow supports Douyin/Xingtu only.",
}

UNSUPPORTED_EXECUTION_SIGNALS = {
    "直播": "Current V1 brief-parse contract targets short-video shortlist generation, not live-stream workflows.",
    "live stream": "Current V1 brief-parse contract targets short-video shortlist generation, not live-stream workflows.",
    "livestream": "Current V1 brief-parse contract targets short-video shortlist generation, not live-stream workflows.",
}

AMBIGUITY_PATTERNS = (
    (re.compile(r"(预算|budget).*(左右|看情况|待定|再议|灵活|差不多|around|tbd)", re.IGNORECASE), "budget_total"),
    (re.compile(r"(kpi|目标).*(尽量|看看|差不多|待定|decent|good enough)", re.IGNORECASE), "kpi_goals"),
    (re.compile(r"(平台|platform).*(都可以|都行|待定|maybe)", re.IGNORECASE), "platform"),
    (re.compile(r"(人群|audience).*(泛人群|大众|都可以|看情况|broad)", re.IGNORECASE), "target_audience"),
)

EXPLICIT_PRIORITY_PREFIXES: dict[BriefPriorityColor, tuple[str, ...]] = {
    BriefPriorityColor.RED: ("must", "required", "hard", "必须", "硬性", "need", "需", "红色"),
    BriefPriorityColor.GREEN: ("prefer", "preferred", "ideal", "希望", "优先", "加分", "绿色"),
    BriefPriorityColor.YELLOW: ("optional", "可选", "可协商", "非必须", "黄色", "可谈"),
}


def parse_brief_with_contract(request: BriefParseInput) -> BriefParseOutput:
    """Parse a brief into the repo contract and attach deterministic business diagnostics."""

    validated_request = BriefParseInput.model_validate(request.model_dump(mode="python"))
    requirement, parser_notes = structure_shortlist_requirement(
        raw_text=validated_request.raw_text,
        structured_requirement=validated_request.structured_requirement,
    )

    missing_information = _build_missing_information(requirement)
    ambiguities = _build_ambiguities(validated_request.raw_text or "", requirement)
    contradictions = _build_contradictions(requirement)
    unsupported_requirements = _build_unsupported_requirements(validated_request.raw_text or "")
    defaults_applied = _build_defaults_applied(validated_request.raw_text or "", requirement)
    priority_signals = _build_priority_signals(validated_request.raw_text or "", requirement)
    parse_status = _determine_parse_status(
        missing_information=missing_information,
        ambiguities=ambiguities,
        contradictions=contradictions,
        unsupported_requirements=unsupported_requirements,
    )

    return BriefParseOutput(
        structured_requirement=requirement,
        parse_status=parse_status,
        parser_notes=parser_notes,
        priority_signals=priority_signals,
        missing_information=missing_information,
        ambiguities=ambiguities,
        contradictions=contradictions,
        unsupported_requirements=unsupported_requirements,
        defaults_applied=defaults_applied,
    )


def validate_brief_parse_output(output: BriefParseOutput) -> BriefParseOutput:
    """Deterministically validate an already-built brief-parse payload."""

    return BriefParseOutput.model_validate(output.model_dump(mode="python"))


def _build_missing_information(requirement: ShortlistRequirement) -> list[BriefParseIssue]:
    issues: list[BriefParseIssue] = []

    def add_issue(field: str, message: str, severity: BriefParseIssueSeverity, source_text: str | None = None) -> None:
        issues.append(
            BriefParseIssue(
                code=BriefParseIssueCode.MISSING_FIELD,
                severity=severity,
                field=field,
                message=message,
                source_text=source_text,
            )
        )

    if not requirement.brand:
        add_issue("brand", "Brand name is missing; downstream shortlist review cannot anchor the campaign owner.", BriefParseIssueSeverity.ERROR)
    if not requirement.product_name:
        add_issue("product_name", "Product or SKU-facing offer is missing; creator search intent is under-specified.", BriefParseIssueSeverity.ERROR)
    if not requirement.budget_total:
        add_issue("budget_total", "Budget is missing; budget_cap_per_creator and downstream ranking safeguards cannot be derived.", BriefParseIssueSeverity.ERROR)
    if not requirement.kpi_goals:
        add_issue("kpi_goals", "KPI goals are missing; the parser cannot distinguish exposure, efficiency, and completion priorities.", BriefParseIssueSeverity.ERROR)
    if not requirement.target_audience and not requirement.hard_constraints.audience_traits:
        add_issue("target_audience", "Target audience is missing; creator audience matching will be unreliable.", BriefParseIssueSeverity.ERROR)
    if not requirement.product_category and not requirement.hard_constraints.creator_categories:
        add_issue("product_category", "Creator category or product category is missing; search keyword derivation will stay generic.", BriefParseIssueSeverity.ERROR)
    if not requirement.content_style_tags and not requirement.tone_tags:
        add_issue(
            "content_style_tags",
            "Content style and tone are both missing; content-fit filtering will be weak.",
            BriefParseIssueSeverity.WARNING,
        )
    if not requirement.compliance_notes:
        add_issue(
            "compliance_notes",
            "Compliance notes are missing; human review should confirm ad labeling and sensitive-language restrictions.",
            BriefParseIssueSeverity.WARNING,
        )
    if not requirement.city:
        add_issue(
            "city",
            "City or regional constraint is missing; this is acceptable for nationwide campaigns but should be confirmed.",
            BriefParseIssueSeverity.WARNING,
        )
    return issues


def _build_ambiguities(raw_text: str, requirement: ShortlistRequirement) -> list[BriefParseIssue]:
    issues: list[BriefParseIssue] = []
    if not raw_text:
        return issues

    for pattern, field in AMBIGUITY_PATTERNS:
        match = pattern.search(raw_text)
        if not match:
            continue
        issues.append(
            BriefParseIssue(
                code=BriefParseIssueCode.AMBIGUOUS_FIELD,
                severity=BriefParseIssueSeverity.WARNING,
                field=field,
                message=f"Detected ambiguous language for `{field}`. Human review should confirm the exact requirement.",
                source_text=match.group(0).strip(),
            )
        )

    if requirement.budget_total is None and re.search(r"(预算|budget)", raw_text, re.IGNORECASE):
        issues.append(
            BriefParseIssue(
                code=BriefParseIssueCode.AMBIGUOUS_FIELD,
                severity=BriefParseIssueSeverity.WARNING,
                field="budget_total",
                message="Budget was discussed but could not be normalized into a numeric total.",
                source_text="budget mentioned without a parsable numeric total",
            )
        )
    return issues


def _build_contradictions(requirement: ShortlistRequirement) -> list[BriefParseIssue]:
    issues: list[BriefParseIssue] = []
    exclusions_lower = [item.lower() for item in requirement.exclusions]
    candidate_categories = unique_list(
        [
            requirement.product_category or "",
            *requirement.hard_constraints.creator_categories,
            *requirement.preferred_constraints.creator_categories,
        ]
    )
    for category in candidate_categories:
        if not category:
            continue
        signals = [item.lower() for item in CATEGORY_SIGNALS.get(category, [])]
        if any(exclusion in signals or exclusion == category.lower() for exclusion in exclusions_lower):
            issues.append(
                BriefParseIssue(
                    code=BriefParseIssueCode.CONTRADICTORY_FIELD,
                    severity=BriefParseIssueSeverity.ERROR,
                    field="exclusions",
                    message=f"Category `{category}` is both requested and excluded.",
                    source_text=category,
                )
            )
    return issues


def _build_unsupported_requirements(raw_text: str) -> list[BriefParseIssue]:
    issues: list[BriefParseIssue] = []
    lowered = raw_text.lower()
    for token, message in UNSUPPORTED_PLATFORM_SIGNALS.items():
        if token.lower() in lowered:
            issues.append(
                BriefParseIssue(
                    code=BriefParseIssueCode.UNSUPPORTED_REQUIREMENT,
                    severity=BriefParseIssueSeverity.ERROR,
                    field="platform",
                    message=message,
                    source_text=token,
                )
            )
    for token, message in UNSUPPORTED_EXECUTION_SIGNALS.items():
        if token.lower() in lowered:
            issues.append(
                BriefParseIssue(
                    code=BriefParseIssueCode.UNSUPPORTED_REQUIREMENT,
                    severity=BriefParseIssueSeverity.ERROR,
                    field="content_form",
                    message=message,
                    source_text=token,
                )
            )
    return issues


def _build_defaults_applied(raw_text: str, requirement: ShortlistRequirement) -> list[str]:
    defaults: list[str] = []
    lowered = raw_text.lower()
    if not any(token in lowered for token in ("douyin", "抖音", "xingtu", "星图", "platform", "平台")):
        defaults.append("platform defaulted to `douyin` for V1 shortlist compatibility.")
    if requirement.hard_constraints.min_fans_count is not None:
        defaults.append("min_fans_count was derived heuristically from budget_total and KPI signals.")
    if requirement.hard_constraints.budget_cap_per_creator is not None:
        defaults.append("budget_cap_per_creator was derived as 35% of budget_total.")
    return unique_list(defaults)


def _build_priority_signals(raw_text: str, requirement: ShortlistRequirement) -> list[BriefPrioritySignal]:
    signals: list[BriefPrioritySignal] = []
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    for line in lines:
        lowered = line.lower()
        for color, prefixes in EXPLICIT_PRIORITY_PREFIXES.items():
            if any(lowered.startswith(prefix) for prefix in prefixes):
                signals.append(
                    BriefPrioritySignal(
                        field="explicit_priority_note",
                        value=line,
                        priority_color=color,
                        mapped_bucket=_color_to_bucket(color),
                        rationale="Explicit priority language in the brief was preserved as a structured signal.",
                        source_text=line,
                    )
                )
                break

    signals.extend(
        _signals_from_values(
            field="hard_constraints.creator_categories",
            values=requirement.hard_constraints.creator_categories,
            priority_color=BriefPriorityColor.RED,
            mapped_bucket=BriefConstraintBucketName.HARD,
            rationale="Core category signals are mapped into hard_constraints for downstream filtering.",
        )
    )
    signals.extend(
        _signals_from_values(
            field="hard_constraints.cities",
            values=requirement.hard_constraints.cities,
            priority_color=BriefPriorityColor.RED,
            mapped_bucket=BriefConstraintBucketName.HARD,
            rationale="Explicit city constraints or normalized city signals are mapped into hard_constraints.",
        )
    )
    signals.extend(
        _signals_from_values(
            field="hard_constraints.audience_traits",
            values=requirement.hard_constraints.audience_traits,
            priority_color=BriefPriorityColor.RED,
            mapped_bucket=BriefConstraintBucketName.HARD,
            rationale="Audience traits needed for shortlist filtering are mapped into hard_constraints.",
        )
    )
    signals.extend(
        _signals_from_values(
            field="preferred_constraints.notes",
            values=requirement.preferred_constraints.notes,
            priority_color=BriefPriorityColor.GREEN,
            mapped_bucket=BriefConstraintBucketName.PREFERRED,
            rationale="Preference notes remain visible for scouting and ranking without becoming hard blockers.",
        )
    )
    signals.extend(
        _signals_from_values(
            field="negotiable_constraints.notes",
            values=requirement.negotiable_constraints.notes,
            priority_color=BriefPriorityColor.YELLOW,
            mapped_bucket=BriefConstraintBucketName.NEGOTIABLE,
            rationale="Negotiable or optional notes are preserved for later shortlist review and outreach.",
        )
    )
    signals.extend(
        _signals_from_values(
            field="compliance_notes",
            values=requirement.compliance_notes,
            priority_color=BriefPriorityColor.RED,
            mapped_bucket=BriefConstraintBucketName.HARD,
            rationale="Compliance notes are treated as red-line constraints for downstream review.",
        )
    )
    signals.extend(
        _signals_from_values(
            field="optional_notes",
            values=requirement.optional_notes,
            priority_color=BriefPriorityColor.YELLOW,
            mapped_bucket=BriefConstraintBucketName.NEGOTIABLE,
            rationale="Optional notes remain negotiable unless explicitly elevated by business review.",
        )
    )
    return signals


def _signals_from_values(
    field: str,
    values: list[str],
    priority_color: BriefPriorityColor,
    mapped_bucket: BriefConstraintBucketName,
    rationale: str,
) -> list[BriefPrioritySignal]:
    return [
        BriefPrioritySignal(
            field=field,
            value=value,
            priority_color=priority_color,
            mapped_bucket=mapped_bucket,
            rationale=rationale,
        )
        for value in unique_list(values)
        if value
    ]


def _determine_parse_status(
    *,
    missing_information: list[BriefParseIssue],
    ambiguities: list[BriefParseIssue],
    contradictions: list[BriefParseIssue],
    unsupported_requirements: list[BriefParseIssue],
) -> BriefParseStatus:
    if contradictions:
        return BriefParseStatus.NEEDS_REVIEW
    if any(item.severity == BriefParseIssueSeverity.ERROR for item in unsupported_requirements):
        return BriefParseStatus.NEEDS_REVIEW
    if ambiguities and any(item.severity == BriefParseIssueSeverity.ERROR for item in ambiguities):
        return BriefParseStatus.NEEDS_REVIEW
    if any(item.severity == BriefParseIssueSeverity.ERROR for item in missing_information):
        return BriefParseStatus.PARTIAL
    if ambiguities or missing_information or unsupported_requirements:
        return BriefParseStatus.PARTIAL
    return BriefParseStatus.COMPLETE


def _color_to_bucket(color: BriefPriorityColor) -> BriefConstraintBucketName:
    if color == BriefPriorityColor.RED:
        return BriefConstraintBucketName.HARD
    if color == BriefPriorityColor.GREEN:
        return BriefConstraintBucketName.PREFERRED
    return BriefConstraintBucketName.NEGOTIABLE
