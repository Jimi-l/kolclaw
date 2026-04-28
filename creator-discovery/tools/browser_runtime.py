from __future__ import annotations

import random
import time
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterator, Optional

from utils import configure_logger, ensure_dir, env_flag


@dataclass
class BrowserRuntimeConfig:
    mock_mode: bool = True
    headless: bool = False
    action_delay_min: float = 0.5
    action_delay_max: float = 1.5
    screenshot_dir: Path = Path("data/screenshots")


class BrowserSession:
    def __init__(self, site_name: str, config: BrowserRuntimeConfig, logger_name: str = "browser_runtime") -> None:
        self.site_name = site_name
        self.config = config
        self.logger = configure_logger(logger_name, Path(config.screenshot_dir).parents[0] / "logs")
        self.current_url: Optional[str] = None
        self.started_at = time.time()
        ensure_dir(self.config.screenshot_dir)

    def goto(self, url: str) -> dict[str, Any]:
        self.current_url = url
        self.logger.info("Open %s session page: %s", self.site_name, url)
        if not self.config.mock_mode:
            raise NotImplementedError("TODO: wire a real browser backend in BrowserSession.goto()")
        self._human_pause()
        return {"url": url, "site_name": self.site_name, "mock_mode": True}

    def ensure_logged_in(self, expected_hint: str | None = None) -> bool:
        self.logger.info("Check login state for %s", self.site_name)
        if expected_hint:
            self.logger.info("Expected login hint: %s", expected_hint)
        if self.config.mock_mode:
            return True
        raise NotImplementedError("TODO: implement live login check and cookie/session reuse")

    def press(self, key: str) -> None:
        self.logger.info("Press key: %s", key)
        if not self.config.mock_mode:
            raise NotImplementedError("TODO: implement live key press support")
        self._human_pause()

    def click(self, target: str) -> None:
        self.logger.info("Click target: %s", target)
        if not self.config.mock_mode:
            raise NotImplementedError("TODO: implement live click support")
        self._human_pause()

    def scroll_feed(self, direction: str = "down") -> None:
        self.logger.info("Scroll feed: %s", direction)
        if not self.config.mock_mode:
            raise NotImplementedError("TODO: implement live feed scroll with real browser actions")
        self._human_pause()

    def pause_video(self) -> None:
        self.logger.info("Pause current video")
        if not self.config.mock_mode:
            raise NotImplementedError("TODO: implement live video pause logic")
        self._human_pause()

    def capture_screenshot(self, label: str) -> str:
        safe_label = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in label)
        file_path = Path(self.config.screenshot_dir) / f"{safe_label}.png"
        ensure_dir(file_path.parent)
        if self.config.mock_mode:
            file_path.write_bytes(b"")
        else:
            raise NotImplementedError("TODO: implement live screenshot capture")
        self.logger.info("Saved screenshot placeholder: %s", file_path)
        return str(file_path)

    def extract_text(self, description: str) -> Optional[str]:
        self.logger.info("Extract text placeholder: %s", description)
        if self.config.mock_mode:
            return None
        raise NotImplementedError("TODO: implement live text extraction")

    def close(self) -> None:
        self.logger.info("Close %s session after %.2fs", self.site_name, time.time() - self.started_at)

    def _human_pause(self) -> None:
        delay = random.uniform(self.config.action_delay_min, self.config.action_delay_max)
        time.sleep(min(delay, 0.05))


class BrowserRuntime:
    def __init__(self, config: Optional[BrowserRuntimeConfig] = None) -> None:
        self.config = config or BrowserRuntimeConfig(
            mock_mode=env_flag("BROWSER_MOCK_MODE", True),
        )
        ensure_dir(self.config.screenshot_dir)
        self.logger = configure_logger("browser_runtime", Path(self.config.screenshot_dir).parents[0] / "logs")
        self.is_started = False

    def start(self) -> None:
        self.logger.info("Browser runtime start (mock_mode=%s)", self.config.mock_mode)
        self.is_started = True

    def stop(self) -> None:
        self.logger.info("Browser runtime stop")
        self.is_started = False

    @contextmanager
    def session(self, site_name: str) -> Iterator[BrowserSession]:
        if not self.is_started:
            self.start()
        session = BrowserSession(site_name=site_name, config=self.config)
        try:
            yield session
        finally:
            session.close()
