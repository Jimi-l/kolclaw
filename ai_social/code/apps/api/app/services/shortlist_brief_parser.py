from __future__ import annotations

import re

from app.schemas.shortlist import RequirementConstraintBucket, ShortlistRequirement
from app.utils.normalization import unique_list

KNOWN_CITIES = {
    "shanghai": "shanghai",
    "上海": "shanghai",
    "beijing": "beijing",
    "北京": "beijing",
    "guangzhou": "guangzhou",
    "广州": "guangzhou",
    "shenzhen": "shenzhen",
    "深圳": "shenzhen",
    "hangzhou": "hangzhou",
    "杭州": "hangzhou",
    "chengdu": "chengdu",
    "成都": "chengdu",
}

CATEGORY_SIGNALS = {
    "美妆": ["beauty", "makeup", "cosmetic", "lip", "lipstick", "skincare", "护肤", "彩妆", "口红", "美妆", "妆容", "种草"],
    "穿搭": ["fashion", "outfit", "stylish", "wardrobe", "runway", "穿搭", "时尚", "造型", "服饰", "ootd"],
    "生活方式": ["lifestyle", "daily", "生活", "vlog", "好物", "city walk"],
    "母婴": ["parenting", "baby", "mom", "mother", "母婴", "育儿"],
    "宠物": ["pet", "pets", "猫", "狗", "宠物"],
}

STYLE_SIGNALS = {
    "种草": ["seeding", "seed", "种草", "测评"],
    "教程感": ["tutorial", "how-to", "教程", "教学", "step"],
    "高级感": ["premium", "luxury", "elevated", "高级", "质感"],
    "真实感": ["real", "authentic", "真实", "自然"],
    "快剪": ["transition", "quick cut", "快剪", "转场"],
    "到店场景": ["offline", "store", "event", "线下", "到店"],
}

TONE_SIGNALS = {
    "可信": ["trustworthy", "credible", "专业", "可信"],
    "都市感": ["city", "urban", "city chic", "都市"],
    "轻松感": ["relaxed", "easy", "轻松", "自然"],
    "精致感": ["polished", "clean", "精致", "干净"],
}

AUDIENCE_SIGNALS = {
    "女性": ["female", "women", "woman", "girl", "女生", "女性", "女白领"],
    "都市白领": ["office", "white collar", "urban", "白领", "上班族"],
    "年轻消费人群": ["young", "gen z", "millennial", "年轻", "学生", "初入职场"],
    "精致消费人群": ["premium", "beauty shopper", "quality seeker", "精致", "品质"],
}

KPI_SIGNALS = {
    "播放量稳定": ["play", "view", "播放", "曝光"],
    "种草效率": ["seed", "种草", "收藏", "转化"],
    "互动质量": ["engagement", "互动", "评论", "收藏"],
    "完播率": ["completion", "完播"],
    "成本效率": ["cpm", "cpe", "cost", "效率"],
}

EXCLUSION_SIGNALS = ["avoid", "exclude", "excluding", "不要", "避免", "排除", "禁", "不接"]
HARD_PREFIXES = ("must", "required", "hard", "必须", "硬性", "need", "需")
PREFERRED_PREFIXES = ("prefer", "preferred", "ideal", "希望", "优先", "加分")
NEGOTIABLE_PREFIXES = ("nice to have", "negotiable", "optional", "可选", "可协商", "非必须")


def structure_shortlist_requirement(
    raw_text: str | None,
    structured_requirement: ShortlistRequirement | None,
) -> tuple[ShortlistRequirement, list[str]]:
    if structured_requirement is not None:
        return structured_requirement, ["Validated provided structured shortlist requirement."]
    if not raw_text or not raw_text.strip():
        raise ValueError("raw_text is required when structured_requirement is omitted.")
    return parse_shortlist_brief(raw_text)


def parse_shortlist_brief(raw_text: str) -> tuple[ShortlistRequirement, list[str]]:
    text = raw_text.strip()
    lower = text.lower()
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    positive_text = "\n".join(
        line for line in lines if not any(signal in line.lower() for signal in EXCLUSION_SIGNALS)
    ).lower()

    parser_notes = ["Parsed brief with deterministic keyword and pattern rules."]

    brand = _extract_field(text, "brand", "品牌")
    product_name = _extract_field(text, "product", "产品", "品名")
    product_sku = _extract_field(text, "sku", "货号", "型号")
    platform = "douyin" if any(token in lower for token in ("douyin", "抖音", "xingtu", "星图")) else "douyin"
    city = _extract_city(text)
    budget_total = _extract_budget(text)

    product_category = _detect_primary_category(positive_text)
    creator_categories = unique_list(_detect_categories(positive_text))
    target_audience = unique_list(_detect_targets(positive_text))
    kpi_goals = unique_list(_detect_kpis(positive_text))
    content_style_tags = unique_list(_detect_styles(positive_text))
    tone_tags = unique_list(_detect_tones(positive_text))

    exclusions = unique_list(_extract_list_field(text, "avoid", "exclude", "exclusions", "排除", "避免"))
    compliance_notes = unique_list(_extract_list_field(text, "compliance", "合规", "注意"))
    optional_notes = unique_list(_extract_list_field(text, "note", "notes", "备注"))

    explicit_hard_notes = _collect_bucket_notes(lines, HARD_PREFIXES)
    explicit_preferred_notes = _collect_bucket_notes(lines, PREFERRED_PREFIXES)
    explicit_negotiable_notes = _collect_bucket_notes(lines, NEGOTIABLE_PREFIXES)

    if platform == "douyin":
        parser_notes.append("Defaulted platform to `douyin` / Xingtu-compatible flow.")
    if product_category:
        parser_notes.append(f"Detected primary creator category `{product_category}`.")
    if city:
        parser_notes.append(f"Detected city `{city}`.")
    if budget_total is not None:
        parser_notes.append(f"Detected budget `{budget_total:,.0f}`.")

    min_fans_count = _derive_min_fans(budget_total, kpi_goals)
    budget_cap_per_creator = round(budget_total * 0.35, 2) if budget_total is not None else None
    keywords = unique_list(
        [
            brand or "",
            product_name or "",
            product_sku or "",
            product_category or "",
            city or "",
            *creator_categories,
            *target_audience,
            *kpi_goals,
            *content_style_tags,
            *tone_tags,
        ]
    )

    hard_constraints = RequirementConstraintBucket(
        creator_categories=creator_categories[:2],
        cities=[city] if city else [],
        content_themes=content_style_tags[:2],
        audience_traits=target_audience[:2],
        exclusions=unique_list(exclusions + _extract_exclusion_hits(lines)),
        min_fans_count=min_fans_count,
        budget_cap_per_creator=budget_cap_per_creator,
        notes=unique_list(explicit_hard_notes + compliance_notes),
    )
    preferred_constraints = RequirementConstraintBucket(
        creator_categories=creator_categories[2:],
        cities=[],
        content_themes=content_style_tags,
        audience_traits=target_audience,
        exclusions=[],
        notes=unique_list(explicit_preferred_notes + ["Prefer creators whose tags visibly match the brand brief."]),
    )
    negotiable_constraints = RequirementConstraintBucket(
        creator_categories=[],
        cities=[],
        content_themes=[],
        audience_traits=[],
        exclusions=[],
        notes=unique_list(explicit_negotiable_notes + optional_notes),
    )

    requirement = ShortlistRequirement(
        brand=brand,
        product_name=product_name,
        product_sku=product_sku,
        product_category=product_category,
        platform=platform,
        city=city,
        target_audience=target_audience,
        kpi_goals=kpi_goals,
        budget_total=budget_total,
        content_style_tags=content_style_tags,
        tone_tags=tone_tags,
        compliance_notes=compliance_notes,
        exclusions=hard_constraints.exclusions,
        optional_notes=optional_notes,
        keywords=keywords,
        hard_constraints=hard_constraints,
        preferred_constraints=preferred_constraints,
        negotiable_constraints=negotiable_constraints,
    )
    return requirement, parser_notes


def _extract_field(text: str, *labels: str) -> str | None:
    for label in labels:
        pattern = re.compile(rf"(?:^|\n)\s*{re.escape(label)}\s*[:：]\s*(.+)", re.IGNORECASE)
        match = pattern.search(text)
        if match:
            value = match.group(1).strip()
            return value or None
    return None


def _extract_list_field(text: str, *labels: str) -> list[str]:
    values: list[str] = []
    for label in labels:
        pattern = re.compile(rf"(?:^|\n)\s*{re.escape(label)}\s*[:：]\s*(.+)", re.IGNORECASE)
        match = pattern.search(text)
        if not match:
            continue
        values.extend(_split_items(match.group(1)))
    return values


def _split_items(value: str) -> list[str]:
    return [item.strip() for item in re.split(r"[，,;/、|]", value) if item.strip()]


def _extract_city(text: str) -> str | None:
    for raw_city, normalized in KNOWN_CITIES.items():
        if raw_city.lower() in text.lower():
            return normalized
    return None


def _extract_budget(text: str) -> float | None:
    patterns = (
        r"(?:budget|预算)[^\d]{0,8}([\d,]+(?:\.\d+)?)",
        r"([\d,]{4,}(?:\.\d+)?)\s*(?:rmb|cny|yuan|元)",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return float(match.group(1).replace(",", ""))
    return None


def _detect_primary_category(lower_text: str) -> str | None:
    categories = _detect_categories(lower_text)
    return categories[0] if categories else None


def _detect_categories(lower_text: str) -> list[str]:
    detected: list[str] = []
    for category, keywords in CATEGORY_SIGNALS.items():
        if any(keyword.lower() in lower_text for keyword in keywords):
            detected.append(category)
    return detected


def _detect_styles(lower_text: str) -> list[str]:
    detected: list[str] = []
    for tag, keywords in STYLE_SIGNALS.items():
        if any(keyword.lower() in lower_text for keyword in keywords):
            detected.append(tag)
    return detected


def _detect_tones(lower_text: str) -> list[str]:
    detected: list[str] = []
    for tag, keywords in TONE_SIGNALS.items():
        if any(keyword.lower() in lower_text for keyword in keywords):
            detected.append(tag)
    return detected


def _detect_targets(lower_text: str) -> list[str]:
    detected: list[str] = []
    for tag, keywords in AUDIENCE_SIGNALS.items():
        if any(keyword.lower() in lower_text for keyword in keywords):
            detected.append(tag)
    return detected


def _detect_kpis(lower_text: str) -> list[str]:
    detected: list[str] = []
    for tag, keywords in KPI_SIGNALS.items():
        if any(keyword.lower() in lower_text for keyword in keywords):
            detected.append(tag)
    return detected


def _collect_bucket_notes(lines: list[str], prefixes: tuple[str, ...]) -> list[str]:
    matched: list[str] = []
    for line in lines:
        lower_line = line.lower()
        if any(lower_line.startswith(prefix) for prefix in prefixes):
            matched.append(line)
    return matched


def _extract_exclusion_hits(lines: list[str]) -> list[str]:
    hits: list[str] = []
    for line in lines:
        lower_line = line.lower()
        if any(signal in lower_line for signal in EXCLUSION_SIGNALS):
            hits.extend(_split_items(re.split(r"[:：]", line, maxsplit=1)[-1]))
    return hits


def _derive_min_fans(budget_total: float | None, kpi_goals: list[str]) -> int | None:
    if budget_total is None:
        return 100000

    if budget_total >= 100000:
        baseline = 250000
    elif budget_total >= 60000:
        baseline = 180000
    elif budget_total >= 30000:
        baseline = 100000
    else:
        baseline = 60000

    if any(goal in {"播放量稳定", "种草效率"} for goal in kpi_goals):
        baseline += 50000
    return baseline
