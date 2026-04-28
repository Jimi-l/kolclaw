from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

from search_agent.enums import WorkflowStage


def slugify_filename(value: str) -> str:
    cleaned = []
    for char in value.lower().strip():
        if char.isalnum():
            cleaned.append(char)
        elif char in {"-", "_"}:
            cleaned.append(char)
        elif char.isspace():
            cleaned.append("_")
    slug = "".join(cleaned).strip("_")
    return slug or "artifact"


@dataclass(slots=True)
class ArtifactManager:
    root: Path
    stage: WorkflowStage
    run_id: str
    run_dir: Path
    screenshots_dir: Path
    logs_dir: Path
    log_path: Path

    @classmethod
    def create(cls, root: Path, stage: WorkflowStage) -> "ArtifactManager":
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_id = f"{stage.value}_{timestamp}"
        run_dir = root / "runs" / run_id
        screenshots_dir = root / "screenshots" / run_id
        logs_dir = root / "logs"
        for path in (run_dir, screenshots_dir, logs_dir):
            path.mkdir(parents=True, exist_ok=True)
        log_path = logs_dir / f"{run_id}.log"
        return cls(
            root=root,
            stage=stage,
            run_id=run_id,
            run_dir=run_dir,
            screenshots_dir=screenshots_dir,
            logs_dir=logs_dir,
            log_path=log_path,
        )

    def screenshot_path(self, label: str, extension: str = "png") -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = f"{timestamp}_{slugify_filename(label)}.{extension.lstrip('.')}"
        return self.screenshots_dir / name

    def write_text(self, label: str, lines: Iterable[str]) -> Path:
        path = self.run_dir / f"{slugify_filename(label)}.txt"
        path.write_text("\n".join(lines), encoding="utf-8")
        return path
