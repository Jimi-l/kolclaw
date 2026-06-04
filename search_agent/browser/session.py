from __future__ import annotations

from pathlib import Path
from typing import Any

from search_agent.config import BrowserConfig
from search_agent.exceptions import MissingDependencyError


class BrowserSession:
    def __init__(self, browser_config: BrowserConfig, user_data_dir: Path):
        self.browser_config = browser_config
        self.user_data_dir = user_data_dir
        self.reused_existing_session = False
        self._playwright = None
        self.context = None
        self.page = None

    def __enter__(self) -> "BrowserSession":
        try:
            from playwright.sync_api import sync_playwright
        except ModuleNotFoundError as exc:
            raise MissingDependencyError(
                "Playwright is not installed. Run `python3 -m pip install -e search_agent` and "
                "`python3 -m playwright install chromium` before using the browser workflows."
            ) from exc

        self.reused_existing_session = self.user_data_dir.exists() and any(self.user_data_dir.iterdir())
        self.user_data_dir.mkdir(parents=True, exist_ok=True)
        self._playwright = sync_playwright().start()
        launch_kwargs: dict[str, Any] = {
            "user_data_dir": str(self.user_data_dir),
            "headless": self.browser_config.headless,
            "locale": "zh-CN",
            "viewport": {"width": 1080, "height": 720},
            "ignore_https_errors": True,
            "slow_mo": self.browser_config.slow_mo_ms,
            "args": [
                "--no-first-run",
                "--disable-default-apps",
                "--disable-notifications",
                "--disable-external-protocol-dialog",
                "--disable-features=DownloadBubble,"
                "DownloadBubbleV2",
                
            ],
        }
        if self.browser_config.channel:
            launch_kwargs["channel"] = self.browser_config.channel
        self.context = self._playwright.chromium.launch_persistent_context(**launch_kwargs)
        self.context.set_default_timeout(self.browser_config.timeout_ms)
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        self.page.on("dialog", lambda dialog: dialog.dismiss())
        return self

    def goto(self, url: str) -> Any:
        if self.page is None:
            raise RuntimeError("Browser session has not been started")
        self.page.goto(url, wait_until="domcontentloaded")
        return self.page

    def save_screenshot(self, path: Path, full_page: bool = True) -> str:
        if self.page is None:
            raise RuntimeError("Browser session has not been started")
        path.parent.mkdir(parents=True, exist_ok=True)
        self.page.screenshot(path=str(path), full_page=full_page)
        return str(path)

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.context is not None:
            try:
                self.context.close()
            except Exception as close_exc:
                if not _is_target_closed_error(close_exc):
                    pass
        if self._playwright is not None:
            try:
                self._playwright.stop()
            except Exception:
                pass


def _is_target_closed_error(exc: Exception) -> bool:
    message = str(exc)
    return "Target page, context or browser has been closed" in message or "TargetClosedError" in exc.__class__.__name__
