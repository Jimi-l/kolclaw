from search_agent.adapters.xingtu import selectors
from search_agent.adapters.xingtu.page import XingtuPageAdapter
from search_agent.enums import BlockReason
from search_agent.exceptions import BlockingStateError, PageStructureUncertainError


class _FakeKeyboard:
    def __init__(self) -> None:
        self.pressed: list[str] = []

    def press(self, key: str) -> None:
        self.pressed.append(key)


class _FakeLocator:
    def __init__(self, *, visible: bool = True, text: str = "", click_callback=None) -> None:
        self.first = self
        self.visible = visible
        self.text = text
        self.filled: str | None = None
        self.fill_values: list[str] = []
        self.click_callback = click_callback

    def count(self) -> int:
        return 1 if self.visible else 0

    def is_visible(self, timeout: int = 800) -> bool:
        return self.visible

    def inner_text(self, timeout: int = 800) -> str:
        return self.text

    def click(self) -> None:
        if self.click_callback:
            self.click_callback()
        return None

    def fill(self, value: str) -> None:
        self.filled = value
        self.fill_values.append(value)


class _FakeArtifacts:
    def screenshot_path(self, label: str) -> str:
        return f"{label}.png"


class _FakePage:
    def __init__(
        self,
        url: str = selectors.BASE_URL,
        body_text: str = "达人市场",
        has_market_nav: bool = False,
        has_search_button: bool = True,
    ) -> None:
        self.url = url
        self.body_text = body_text
        self.has_market_nav = has_market_nav
        self.has_search_button = has_search_button
        self.goto_urls: list[str] = []
        self.keyboard = _FakeKeyboard()
        self.search_input = _FakeLocator()
        self.used_search_input_selectors: list[str] = []
        self.search_button_clicks = 0

    def goto(self, url: str, wait_until: str = "domcontentloaded") -> None:
        self.url = url
        self.goto_urls.append(url)

    def wait_for_timeout(self, timeout: int) -> None:
        return None

    def locator(self, selector: str) -> _FakeLocator:
        if selector == "body":
            return _FakeLocator(text=self.body_text)
        if selector in selectors.SEARCH_BUTTON_SELECTORS and self.has_search_button:
            return _FakeLocator(click_callback=self._click_search_button)
        if selector in selectors.SEARCH_INPUT_SELECTORS:
            self.used_search_input_selectors.append(selector)
            return self.search_input
        return _FakeLocator(visible=False)

    def screenshot(self, path: str, full_page: bool = True) -> None:
        return None

    def _click_search_button(self) -> None:
        self.search_button_clicks += 1


class _FakeLogger:
    def info(self, *args, **kwargs) -> None:
        return None


def test_open_homepage_enters_backend_home() -> None:
    page = _FakePage(has_market_nav=True)
    adapter = XingtuPageAdapter(page, artifacts=None, logger=_FakeLogger())

    adapter.open_homepage()

    assert page.goto_urls == [selectors.CREATOR_BACKEND_HOME_URL]
    assert page.url == selectors.CREATOR_BACKEND_HOME_URL


def test_search_uses_backend_home_search_box_without_market_navigation() -> None:
    page = _FakePage(url=f"{selectors.BASE_URL.rstrip('/')}/ad/creator/index", has_market_nav=True)
    adapter = XingtuPageAdapter(page, artifacts=None, logger=_FakeLogger())

    outcome = adapter.search("夏叔厨房")

    assert page.goto_urls == []
    assert page.used_search_input_selectors[0] == "input[placeholder='输入达人昵称、抖音号或星图ID']"
    assert page.search_input.fill_values == ["", "夏叔厨房"]
    assert page.search_input.filled == "夏叔厨房"
    assert page.keyboard.pressed == ["Enter"]
    assert page.search_button_clicks == 1
    assert outcome.result_kind == "not_found"


def test_redirect_uri_wrapper_is_not_treated_as_backend_home() -> None:
    page = _FakePage(url=f"{selectors.BASE_URL}?redirect_uri=/ad/creator/index", has_market_nav=True)
    adapter = XingtuPageAdapter(page, artifacts=None, logger=_FakeLogger())

    adapter.search("澶忓彅鍘ㄦ埧")

    assert page.goto_urls == [selectors.CREATOR_BACKEND_HOME_URL]


def test_missing_search_box_on_public_login_page_is_resumable_login_block() -> None:
    page = _FakePage(url=selectors.CREATOR_BACKEND_HOME_URL, body_text="登录")
    page.search_input = _FakeLocator(visible=False)
    adapter = XingtuPageAdapter(page, artifacts=_FakeArtifacts(), logger=_FakeLogger())

    try:
        adapter.search("夏叔厨房")
    except BlockingStateError as exc:
        assert exc.reason == BlockReason.LOGIN_REQUIRED
        assert exc.resumable is True
    else:
        raise AssertionError("expected a resumable login block")


def test_missing_search_box_on_unknown_market_page_is_resumable_structure_block() -> None:
    page = _FakePage(url=selectors.CREATOR_BACKEND_HOME_URL, body_text="首页")
    page.search_input = _FakeLocator(visible=False)
    adapter = XingtuPageAdapter(page, artifacts=_FakeArtifacts(), logger=_FakeLogger())

    try:
        adapter.search("夏叔厨房")
    except PageStructureUncertainError as exc:
        assert exc.resumable is True
    else:
        raise AssertionError("expected a resumable page structure block")


def test_public_landing_page_without_search_box_is_resumable_structure_block() -> None:
    page = _FakePage(
        url=f"{selectors.BASE_URL}?redirect_uri=/ad/creator/market",
        body_text="达人营销 好内容成就好生意",
    )
    page.search_input = _FakeLocator(visible=False)
    adapter = XingtuPageAdapter(page, artifacts=_FakeArtifacts(), logger=_FakeLogger())

    try:
        adapter.search("夏叔厨房")
    except PageStructureUncertainError as exc:
        assert exc.resumable is True
        assert "公开营销页" in exc.message
    else:
        raise AssertionError("expected a resumable public landing block")
