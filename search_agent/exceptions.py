from __future__ import annotations

from dataclasses import dataclass

from search_agent.enums import BlockReason


class SearchAgentError(Exception):
    """Base exception for the project."""


@dataclass(slots=True)
class BlockingStateError(SearchAgentError):
    reason: BlockReason
    message: str
    page_name: str | None = None
    page_state: str | None = None
    screenshot_path: str | None = None
    required_user_action: str | None = None
    needs_user_action: bool = True
    resumable: bool = False

    def to_note(self) -> str:
        parts = [self.reason.value, self.message]
        if self.page_state:
            parts.append(f"page_state={self.page_state}")
        if self.required_user_action:
            parts.append(f"operator_action={self.required_user_action}")
        if self.resumable:
            parts.append("resumable=true")
        if self.screenshot_path:
            parts.append(f"screenshot={self.screenshot_path}")
        return " | ".join(parts)

    def __str__(self) -> str:
        return self.to_note()


class PageStructureUncertainError(BlockingStateError):
    pass


class MissingDependencyError(SearchAgentError):
    """Raised when an optional runtime dependency is not available."""
