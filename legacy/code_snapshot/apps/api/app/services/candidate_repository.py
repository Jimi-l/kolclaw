from __future__ import annotations

import json
from pathlib import Path

from app.core.config import get_settings
from app.schemas.candidate import CandidateCreator


class CandidateRepository:
    """Repository boundary around local candidate JSON files."""

    def __init__(self, data_dir: Path | None = None) -> None:
        settings = get_settings()
        self.data_dir = data_dir or settings.mock_candidates_dir

    def list_candidates(self) -> list[CandidateCreator]:
        candidates: list[CandidateCreator] = []
        for path in sorted(self.data_dir.glob("*.json")):
            with path.open("r", encoding="utf-8") as file:
                payload = json.load(file)
            if isinstance(payload, list):
                candidates.extend(CandidateCreator.model_validate(item) for item in payload)
            else:
                candidates.append(CandidateCreator.model_validate(payload))
        return candidates
