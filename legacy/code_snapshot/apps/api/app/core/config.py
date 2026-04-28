from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

REPO_ROOT = Path(__file__).resolve().parents[4]


class Settings(BaseModel):
    api_title: str = "KOLClaw API"
    api_prefix: str = "/api"
    repo_root: Path = REPO_ROOT
    strategy_templates_dir: Path = REPO_ROOT / "configs" / "strategy_templates"
    mock_candidates_dir: Path = REPO_ROOT / "data" / "mock_candidates"
    mock_briefs_dir: Path = REPO_ROOT / "data" / "mock_briefs"


@lru_cache
def get_settings() -> Settings:
    return Settings()
