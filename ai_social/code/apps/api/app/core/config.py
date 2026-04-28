from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

CODE_ROOT = Path(__file__).resolve().parents[4]
WORKSPACE_ROOT = CODE_ROOT.parent


class Settings(BaseModel):
    api_title: str = "KOLClaw API"
    api_prefix: str = "/api"
    repo_root: Path = CODE_ROOT
    code_root: Path = CODE_ROOT
    workspace_root: Path = WORKSPACE_ROOT
    strategy_templates_dir: Path = CODE_ROOT / "configs" / "strategy_templates"
    mock_candidates_dir: Path = CODE_ROOT / "data" / "mock_candidates"
    mock_briefs_dir: Path = CODE_ROOT / "data" / "mock_briefs"
    playwright_root: Path = WORKSPACE_ROOT / "playwright"
    playwright_auth_dir: Path = WORKSPACE_ROOT / "playwright" / ".auth"
    tmp_root: Path = WORKSPACE_ROOT / "tmp"
    external_docs_root: Path = WORKSPACE_ROOT / "external_docs"
    external_docs_operational_dir: Path = WORKSPACE_ROOT / "external_docs" / "operational"
    external_docs_strategy_dir: Path = WORKSPACE_ROOT / "external_docs" / "strategy"
    external_docs_archive_dir: Path = WORKSPACE_ROOT / "external_docs" / "archive"
    workspace_tests_dir: Path = WORKSPACE_ROOT / "tests"
    default_xingtu_storage_state: Path = WORKSPACE_ROOT / "playwright" / ".auth" / "xingtu.json"
    default_xingtu_recording: Path = WORKSPACE_ROOT / "tmp" / "recordings" / "xingtu_clean_recording.ts"

    def resolve_storage_state_path(self, value: str | Path | None = None) -> Path:
        if value is None or str(value).strip() == "":
            return self.default_xingtu_storage_state.resolve()

        requested = Path(value).expanduser()
        if requested.is_absolute():
            return requested.resolve()

        candidates = (
            Path.cwd() / requested,
            self.workspace_root / requested,
            self.playwright_root / requested,
            self.playwright_auth_dir / requested,
        )
        for candidate in candidates:
            if candidate.exists():
                return candidate.resolve()

        return (self.workspace_root / requested).resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
