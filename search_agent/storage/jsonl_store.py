from __future__ import annotations

from pathlib import Path
from typing import Generic, TypeVar

from pydantic import BaseModel

from search_agent.utils.jsonl import append_jsonl, read_jsonl, write_jsonl

T = TypeVar("T", bound=BaseModel)


class JsonlStore(Generic[T]):
    def __init__(self, path: Path, model_cls: type[T]):
        self.path = path
        self.model_cls = model_cls
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, record: T) -> None:
        append_jsonl(self.path, record.model_dump(mode="json"))

    def load_all(self) -> list[T]:
        return [self.model_cls.model_validate(item) for item in read_jsonl(self.path)]

    def save_all(self, records: list[T]) -> None:
        write_jsonl(self.path, [record.model_dump(mode="json") for record in records])

    def upsert(self, record: T, key_field: str = "record_id") -> None:
        key = getattr(record, key_field)
        records = self.load_all()
        for index, existing in enumerate(records):
            if getattr(existing, key_field, None) == key:
                records[index] = record
                self.save_all(records)
                return
        records.append(record)
        self.save_all(records)
