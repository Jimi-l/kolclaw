from datetime import date

from search_agent.utils.normalize import (
    format_chinese_count,
    normalize_chinese_count,
    normalize_currency_value,
    normalize_publish_date,
    score_hotness_age,
)


def test_normalize_chinese_count_handles_units() -> None:
    assert normalize_chinese_count("12.5万") == 125000
    assert normalize_chinese_count("3.2亿") == 320000000
    assert normalize_chinese_count("9800") == 9800


def test_normalize_currency_value_handles_units() -> None:
    assert normalize_currency_value("5,200元") == 5200.0
    assert normalize_currency_value("1.26万") == 12600.0


def test_publish_date_and_hotness_score() -> None:
    reference = date(2026, 4, 7)
    assert normalize_publish_date("2天前", reference_date=reference) == "2026-04-05"
    assert normalize_publish_date("3月1日", reference_date=reference) == "2026-03-01"
    assert score_hotness_age("2天前", reference_date=reference) == "90%"
    assert score_hotness_age("20天前", reference_date=reference) == "60%"


def test_format_chinese_count() -> None:
    assert format_chinese_count(358000) == "35.8万"
    assert format_chinese_count(125000000) == "1.2亿"
