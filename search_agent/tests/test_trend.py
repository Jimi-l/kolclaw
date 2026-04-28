from search_agent.enums import TrafficTrend
from search_agent.utils.trend import classify_traffic_trend


def test_classify_traffic_trend_flash() -> None:
    trend, reason, avg = classify_traffic_trend("100万", ["10万", "20万", "15万"])
    assert trend == TrafficTrend.FLASH
    assert "偶发爆款" in reason
    assert avg == "15万"


def test_classify_traffic_trend_volatile() -> None:
    trend, reason, avg = classify_traffic_trend("80万", ["30万", "50万", "40万"])
    assert trend == TrafficTrend.VOLATILE
    assert "流量波动" in reason
    assert avg == "40万"


def test_classify_traffic_trend_sustained() -> None:
    trend, reason, avg = classify_traffic_trend("50万", ["45万", "42万", "40万"])
    assert trend == TrafficTrend.SUSTAINED
    assert "持续爆款" in reason
    assert avg == "42.3万"
