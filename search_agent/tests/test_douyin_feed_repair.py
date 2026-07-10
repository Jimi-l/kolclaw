from __future__ import annotations

import logging
from itertools import chain, repeat

import pytest

from search_agent.adapters.douyin.page import DouyinPageAdapter, PageStateSnapshot
from search_agent.exceptions import BlockingStateError, PageStructureUncertainError


def _adapter() -> DouyinPageAdapter:
    adapter = DouyinPageAdapter.__new__(DouyinPageAdapter)
    adapter.logger = logging.getLogger("test.douyin_feed_repair")
    adapter.page = None
    adapter._jingxuan_recommend_blocked = False
    adapter._jingxuan_recommend_block_reason = None
    adapter._jingxuan_recommend_selected = False
    return adapter


def _snapshot(state: str) -> PageStateSnapshot:
    return PageStateSnapshot(
        state=state,
        page_url="https://www.douyin.com/",
        page_title="抖音-记录美好生活",
        reason="missing anchors",
        missing_readiness_anchors=["active_feed_item", "creator_name", "creator_anchor", "video_anchor", "interaction_metric"],
    )


def test_public_feed_gate_repairs_before_resumable_pause() -> None:
    adapter = _adapter()
    states = iter([_snapshot("public_feed"), _snapshot("recommend_feed_interactable")])
    repaired_states: list[str] = []
    adapter.classify_page_state = lambda **_kwargs: next(states)  # type: ignore[method-assign]

    def fake_repair(snapshot: PageStateSnapshot, bootstrap_login: bool) -> bool:
        repaired_states.append(snapshot.state)
        return True

    adapter._attempt_ready_state_repair = fake_repair  # type: ignore[method-assign]

    result = adapter.ensure_normal_feed()

    assert repaired_states == ["public_feed"]
    assert result.state == "recommend_feed_interactable"


def test_public_feed_gate_pauses_only_after_repair_fails() -> None:
    adapter = _adapter()
    adapter.classify_page_state = lambda **_kwargs: _snapshot("public_feed")  # type: ignore[method-assign]
    adapter._attempt_ready_state_repair = lambda *_args, **_kwargs: False  # type: ignore[method-assign]

    with pytest.raises(BlockingStateError) as exc_info:
        adapter.ensure_normal_feed()

    assert exc_info.value.page_state == "public_feed"


def test_public_feed_repair_tries_multiple_feed_actions() -> None:
    adapter = _adapter()
    actions: list[str] = []

    class FakeMouse:
        def wheel(self, x: int, y: int) -> None:
            actions.append(f"wheel:{x}:{y}")

    class FakeKeyboard:
        def press(self, key: str) -> None:
            actions.append(f"key:{key}")

    class FakePage:
        url = "https://www.douyin.com/"
        mouse = FakeMouse()
        keyboard = FakeKeyboard()

        def is_closed(self) -> bool:
            return False

        def goto(self, url: str, wait_until: str, timeout: int) -> None:
            actions.append(f"goto:{url}:{wait_until}:{timeout}")
            self.url = url

    adapter.page = FakePage()
    adapter._safe_title = lambda: "抖音-记录美好生活"  # type: ignore[method-assign]
    adapter._enter_recommendation_feed = lambda: False  # type: ignore[method-assign]
    adapter._click_next_feed_arrow = lambda **_kwargs: False  # type: ignore[method-assign]
    adapter._wait_for_timeout_safe = lambda *_args, **_kwargs: True  # type: ignore[method-assign]
    states = iter([_snapshot("recommend_feed_interactable")])
    adapter.classify_page_state = lambda **_kwargs: next(states)  # type: ignore[method-assign]

    repaired = adapter._repair_feed_surface_state(_snapshot("public_feed"))

    assert repaired is True
    assert actions == ["wheel:0:900"]


def test_enter_recommend_feed_from_jingxuan_falls_back_when_click_stays_stuck() -> None:
    adapter = _adapter()
    actions: list[str] = []

    class FakeLocator:
        def scroll_into_view_if_needed(self, timeout: int) -> None:
            actions.append(f"scroll:{timeout}")

        def click(self, timeout: int) -> None:
            actions.append(f"click:{timeout}")

    class FakeKeyboard:
        def press(self, key: str) -> None:
            actions.append(f"key:{key}")

    class FakeMouse:
        def wheel(self, x: int, y: int) -> None:
            actions.append(f"wheel:{x}:{y}")

    class FakePage:
        url = "https://www.douyin.com/jingxuan"
        keyboard = FakeKeyboard()
        mouse = FakeMouse()

        def is_closed(self) -> bool:
            return False

        def goto(self, url: str, wait_until: str, timeout: int) -> None:
            actions.append(f"goto:{url}:{wait_until}:{timeout}")
            self.url = url

        def wait_for_timeout(self, timeout_ms: int) -> None:
            actions.append(f"wait:{timeout_ms}")

    states = iter([_snapshot("public_jingxuan_landing"), _snapshot("recommend_feed_shell")])
    adapter.page = FakePage()
    adapter._ensure_page_open = lambda **_kwargs: True  # type: ignore[method-assign]
    adapter._safe_title = lambda: "抖音-记录美好生活"  # type: ignore[method-assign]
    adapter._wait_for_timeout_safe = lambda *_args, **_kwargs: True  # type: ignore[method-assign]
    adapter._find_jingxuan_recommend_target = lambda timeout_ms=800: FakeLocator()  # type: ignore[method-assign]
    adapter.classify_page_state = lambda **_kwargs: next(states)  # type: ignore[method-assign]

    assert adapter.enter_recommend_feed_from_jingxuan() is True
    assert any(action.startswith("goto:https://www.douyin.com/?recommend=1&from_nav=1") for action in actions)


def test_enter_recommend_feed_from_jingxuan_returns_false_when_still_on_jingxuan() -> None:
    adapter = _adapter()

    class FakeLocator:
        def scroll_into_view_if_needed(self, timeout: int) -> None:
            return None

        def click(self, timeout: int) -> None:
            return None

    class FakeKeyboard:
        def press(self, key: str) -> None:
            return None

    class FakeMouse:
        def wheel(self, x: int, y: int) -> None:
            return None

    class FakePage:
        url = "https://www.douyin.com/jingxuan"
        keyboard = FakeKeyboard()
        mouse = FakeMouse()

        def is_closed(self) -> bool:
            return False

        def goto(self, url: str, wait_until: str, timeout: int) -> None:
            self.url = url

        def wait_for_timeout(self, timeout_ms: int) -> None:
            return None

    states = iter([_snapshot("public_jingxuan_landing"), _snapshot("public_jingxuan_landing")])
    adapter.page = FakePage()
    adapter._ensure_page_open = lambda **_kwargs: True  # type: ignore[method-assign]
    adapter._safe_title = lambda: "抖音-记录美好生活"  # type: ignore[method-assign]
    adapter._wait_for_timeout_safe = lambda *_args, **_kwargs: True  # type: ignore[method-assign]
    adapter._find_jingxuan_recommend_target = lambda timeout_ms=800: FakeLocator()  # type: ignore[method-assign]
    adapter.classify_page_state = lambda **_kwargs: next(states)  # type: ignore[method-assign]

    assert adapter.enter_recommend_feed_from_jingxuan() is False


def test_self_profile_is_not_treated_as_creator_homepage() -> None:
    assert DouyinPageAdapter._looks_like_self_profile("https://www.douyin.com/user/self?from_tab_name=main")
    assert DouyinPageAdapter._looks_like_self_profile("https://www.douyin.com/user/MS4w?sec_user_id=self")
    assert not DouyinPageAdapter._looks_like_self_profile("https://www.douyin.com/user/MS4wLjABAAAAcreator")


def test_f_key_self_profile_misnavigation_is_recovered_not_success() -> None:
    adapter = _adapter()
    states = chain(
        [
            _snapshot("recommend_feed_interactable"),
            _snapshot("recommend_feed_interactable"),
            PageStateSnapshot(state="self_profile_open", page_url="https://www.douyin.com/user/self?from_tab_name=main"),
            _snapshot("recommend_feed_interactable"),
        ],
        repeat(_snapshot("recommend_feed_interactable")),
    )
    recovery_calls: list[str | None] = []

    class FakeKeyboard:
        def press(self, key: str) -> None:
            assert key == "f"

    class FakePage:
        url = "https://www.douyin.com/?recommend=1&from_nav=1"
        keyboard = FakeKeyboard()

        def is_closed(self) -> bool:
            return False

    adapter.page = FakePage()
    adapter.classify_page_state = lambda **_kwargs: next(states)  # type: ignore[method-assign]
    adapter._extract_active_feed_state = lambda: {"creator_profile_url": "https://www.douyin.com/user/creator", "active_text": "作者 视频 点赞 评论"}  # type: ignore[method-assign]
    adapter._focus_active_feed = lambda _state: None  # type: ignore[method-assign]
    adapter._safe_title = lambda: "抖音-记录美好生活"  # type: ignore[method-assign]
    adapter._wait_for_timeout_safe = lambda *_args, **_kwargs: True  # type: ignore[method-assign]
    adapter._recover_from_self_profile = lambda debug_label=None: recovery_calls.append(debug_label) or True  # type: ignore[method-assign]
    adapter._capture = lambda _label: "/tmp/self-profile.png"  # type: ignore[method-assign]

    with pytest.raises(PageStructureUncertainError):
        adapter.open_creator_homepage_with_f(observation_index=1, debug_label="001")

    assert recovery_calls == ["001"]


def test_panel_close_target_rejects_left_navigation_hotspots() -> None:
    adapter = _adapter()

    class FakePage:
        viewport_size = {"width": 1200, "height": 800}

    class FakeLocator:
        def __init__(self, box: dict[str, int]) -> None:
            self._box = box

        def is_visible(self, timeout: int) -> bool:
            return True

        def bounding_box(self) -> dict[str, int]:
            return self._box

    adapter.page = FakePage()

    assert not adapter._is_likely_panel_close_target(FakeLocator({"x": 80, "y": 64, "width": 40, "height": 40}))
    assert not adapter._is_likely_panel_close_target(FakeLocator({"x": 1120, "y": 8, "width": 24, "height": 24}), min_y=48)
    assert adapter._is_likely_panel_close_target(FakeLocator({"x": 1040, "y": 80, "width": 32, "height": 32}), min_y=48)


def test_feed_side_panel_dismissal_avoids_top_right_hotspot(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = _adapter()
    key_presses: list[str] = []
    mouse_clicks: list[tuple[int, int]] = []
    side_panel_open = {"value": True}

    class FakeKeyboard:
        def press(self, key: str) -> None:
            key_presses.append(key)
            side_panel_open["value"] = False

    class FakeMouse:
        def click(self, x: int, y: int) -> None:
            mouse_clicks.append((x, y))

    class FakePage:
        url = "https://www.douyin.com/?recommend=1"
        viewport_size = {"width": 1200, "height": 800}
        keyboard = FakeKeyboard()
        mouse = FakeMouse()

    adapter.page = FakePage()
    adapter._has_feed_side_panel = lambda: side_panel_open["value"]  # type: ignore[method-assign]
    adapter._wait_for_timeout_safe = lambda *_args, **_kwargs: True  # type: ignore[method-assign]
    adapter._safe_title = lambda: "抖音-记录美好生活"  # type: ignore[method-assign]
    monkeypatch.setattr("search_agent.adapters.douyin.page.first_visible_locator", lambda *_args, **_kwargs: None)

    assert adapter._dismiss_feed_side_panel(reason="test", debug_label="001")
    assert key_presses == ["Escape"]
    assert mouse_clicks == []
