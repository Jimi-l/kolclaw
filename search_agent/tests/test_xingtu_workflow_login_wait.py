from types import SimpleNamespace

from search_agent.adapters.xingtu import selectors
from search_agent.adapters.xingtu.workflow import XingtuEnrichmentWorkflow
from search_agent.enums import BlockReason
from search_agent.exceptions import BlockingStateError


class _FakeLogger:
    def info(self, *args, **kwargs) -> None:
        return None

    def warning(self, *args, **kwargs) -> None:
        return None

    def debug(self, *args, **kwargs) -> None:
        return None


class _FakeBodyLocator:
    def __init__(self, page) -> None:
        self.page = page

    def inner_text(self, timeout: int = 800) -> str:
        return self.page.body_text


class _FakePage:
    def __init__(self, url: str = "https://sso.oceanengine.com/xingtu/login", body_text: str = "login") -> None:
        self.url = url
        self.body_text = body_text
        self.wait_count = 0
        self.goto_urls: list[str] = []

    def locator(self, selector: str):
        assert selector == "body"
        return _FakeBodyLocator(self)

    def wait_for_timeout(self, timeout: int) -> None:
        self.wait_count += 1
        self.url = selectors.CREATOR_BACKEND_HOME_URL

    def goto(self, url: str, wait_until: str = "domcontentloaded") -> None:
        self.url = url
        self.goto_urls.append(url)


def test_login_block_waits_for_creator_index_without_terminal_enter() -> None:
    workflow = XingtuEnrichmentWorkflow.__new__(XingtuEnrichmentWorkflow)
    workflow.browser_config = SimpleNamespace(headless=False)
    workflow.logger = _FakeLogger()

    for reason in (BlockReason.LOGIN_REQUIRED, BlockReason.QR_LOGIN_REQUIRED, BlockReason.SMS_LOGIN_REQUIRED):
        page = _FakePage()
        adapter = SimpleNamespace(page=page)
        block = BlockingStateError(
            reason=reason,
            message="login required",
            page_name="xingtu-home",
            resumable=True,
        )

        assert workflow._handle_resumable_pause(block, context="test-login", adapter=adapter) is True
        assert page.url == selectors.CREATOR_BACKEND_HOME_URL
        assert page.wait_count == 1


def test_login_wait_navigates_redirect_uri_wrapper_to_creator_index() -> None:
    workflow = XingtuEnrichmentWorkflow.__new__(XingtuEnrichmentWorkflow)
    workflow.browser_config = SimpleNamespace(headless=False)
    workflow.logger = _FakeLogger()
    page = _FakePage(url=f"{selectors.BASE_URL}?redirect_uri=/ad/creator/index", body_text="home")
    adapter = SimpleNamespace(page=page)
    block = BlockingStateError(
        reason=BlockReason.LOGIN_REQUIRED,
        message="login required",
        page_name="xingtu-home",
        resumable=True,
    )

    assert workflow._handle_resumable_pause(block, context="test-login", adapter=adapter) is True
    assert page.goto_urls == [selectors.CREATOR_BACKEND_HOME_URL]
    assert page.url == selectors.CREATOR_BACKEND_HOME_URL
