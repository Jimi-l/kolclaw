from __future__ import annotations

from pathlib import Path

from search_agent.models.discovery import CreatorDiscoveryRecord
from search_agent.storage.jsonl_store import JsonlStore


class XingtuQueueStore:
    def __init__(self, path: Path):
        self.path = path
        self.store = JsonlStore(path, CreatorDiscoveryRecord)

    def enqueue(self, record: CreatorDiscoveryRecord) -> None:
        self.store.append(record)

    def load_pending(
        self,
        processed_record_ids: set[str] | None = None,
        limit: int | None = None,
        priority_record_ids: set[str] | None = None,
    ) -> list[CreatorDiscoveryRecord]:
        seen = processed_record_ids or set()
        pending = [record for record in self.store.load_all() if record.record_id not in seen]
        if priority_record_ids:
            prioritized = [record for record in pending if record.record_id in priority_record_ids]
            remaining = [record for record in pending if record.record_id not in priority_record_ids]
            pending = prioritized + remaining
        if limit is not None:
            return pending[:limit]
        return pending


class ContentAnalysisQueueStore:
    def __init__(self, path: Path):
        self.path = path
        self.store = JsonlStore(path, CreatorDiscoveryRecord)

    def enqueue(self, record: CreatorDiscoveryRecord) -> None:
        self.store.append(record)

    def load_pending(
        self,
        processed_record_ids: set[str] | None = None,
        limit: int | None = None,
        priority_record_ids: set[str] | None = None,
    ) -> list[CreatorDiscoveryRecord]:
        seen = processed_record_ids or set()
        pending = [record for record in self.store.load_all() if record.record_id not in seen]
        if priority_record_ids:
            prioritized = [record for record in pending if record.record_id in priority_record_ids]
            remaining = [record for record in pending if record.record_id not in priority_record_ids]
            pending = prioritized + remaining
        if limit is not None:
            return pending[:limit]
        return pending
