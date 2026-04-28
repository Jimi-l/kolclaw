from __future__ import annotations

from search_agent.enums import RecordStatus


ALLOWED_TRANSITIONS: dict[RecordStatus, set[RecordStatus]] = {
    RecordStatus.NEW_TASK: {RecordStatus.DISCOVERING, RecordStatus.ENRICHING},
    RecordStatus.DISCOVERING: {RecordStatus.DISCOVERED, RecordStatus.QUEUED_FOR_XINGTU, RecordStatus.SKIPPED, RecordStatus.BLOCKED},
    RecordStatus.DISCOVERED: {RecordStatus.QUEUED_FOR_XINGTU},
    RecordStatus.QUEUED_FOR_XINGTU: {
        RecordStatus.ENRICHING,
        RecordStatus.XINGTU_COMPLETED,
        RecordStatus.XINGTU_NOT_FOUND,
        RecordStatus.XINGTU_UNREGISTERED,
        RecordStatus.AMBIGUOUS_MATCH,
        RecordStatus.FIELD_PARTIAL,
        RecordStatus.BLOCKED,
    },
    RecordStatus.ENRICHING: {
        RecordStatus.XINGTU_COMPLETED,
        RecordStatus.XINGTU_NOT_FOUND,
        RecordStatus.XINGTU_UNREGISTERED,
        RecordStatus.AMBIGUOUS_MATCH,
        RecordStatus.FIELD_PARTIAL,
        RecordStatus.BLOCKED,
    },
}


def can_transition(current: RecordStatus, target: RecordStatus) -> bool:
    return target in ALLOWED_TRANSITIONS.get(current, set())


def assert_transition(current: RecordStatus, target: RecordStatus) -> None:
    if not can_transition(current, target):
        raise ValueError(f"invalid status transition: {current.value} -> {target.value}")
