from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Optional
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from utils import configure_logger, env_flag


@dataclass
class LLMConfig:
    provider: str = "mock"
    model: str = "mock-generic"
    api_base: Optional[str] = None
    api_key: Optional[str] = None
    timeout_seconds: int = 30
    mock_mode: bool = True


class LLMClient:
    def __init__(self, config: Optional[LLMConfig] = None, log_dir: str = "data/logs") -> None:
        self.config = config or LLMConfig(
            provider=os.getenv("LLM_PROVIDER", "mock"),
            model=os.getenv("LLM_MODEL", "mock-generic"),
            api_base=os.getenv("LLM_API_BASE"),
            api_key=os.getenv("LLM_API_KEY"),
            mock_mode=env_flag("LLM_MOCK_MODE", True),
        )
        self.logger = configure_logger("llm_client", log_dir)

    def complete(self, system_prompt: str, user_prompt: str) -> str:
        if self.config.mock_mode or self.config.provider == "mock":
            return self._mock_complete(system_prompt=system_prompt, user_prompt=user_prompt)
        return self._live_complete(system_prompt=system_prompt, user_prompt=user_prompt)

    def json_completion(
        self,
        system_prompt: str,
        user_prompt: str,
        mock_response: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        if self.config.mock_mode or self.config.provider == "mock":
            if mock_response is not None:
                return mock_response
            return {
                "provider": "mock",
                "model": self.config.model,
                "summary": user_prompt[:160],
            }

        response_text = self._live_complete(system_prompt=system_prompt, user_prompt=user_prompt)
        return json.loads(response_text)

    def _mock_complete(self, system_prompt: str, user_prompt: str) -> str:
        self.logger.info("Return mock LLM response")
        summary = user_prompt.strip().replace("\n", " ")
        return f"[mock:{self.config.model}] {summary[:200]}"

    def _live_complete(self, system_prompt: str, user_prompt: str) -> str:
        if not self.config.api_base or not self.config.api_key:
            raise RuntimeError("Live LLM mode requires LLM_API_BASE and LLM_API_KEY")

        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        request = Request(
            url=f"{self.config.api_base.rstrip('/')}/chat/completions",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            },
            method="POST",
        )

        try:
            with urlopen(request, timeout=self.config.timeout_seconds) as response:
                body = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise RuntimeError(f"LLM HTTP error: {exc.code}") from exc
        except URLError as exc:
            raise RuntimeError(f"LLM request failed: {exc.reason}") from exc

        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise RuntimeError("Unexpected LLM response structure") from exc
