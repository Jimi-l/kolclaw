from __future__ import annotations

from pathlib import Path
from typing import Generic, Protocol, TypeVar

from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class ModelStore(Protocol, Generic[T]):
    path: Path

    def append(self, record: T) -> None:
        ...

    def load_all(self) -> list[T]:
        ...
