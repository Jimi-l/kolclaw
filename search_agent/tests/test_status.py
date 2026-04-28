import pytest

from search_agent.enums import RecordStatus
from search_agent.utils.status import assert_transition, can_transition


def test_status_transition_allows_discovery_queue() -> None:
    assert can_transition(RecordStatus.DISCOVERING, RecordStatus.QUEUED_FOR_XINGTU) is True
    assert can_transition(RecordStatus.QUEUED_FOR_XINGTU, RecordStatus.XINGTU_COMPLETED) is True


def test_status_transition_rejects_invalid_path() -> None:
    assert can_transition(RecordStatus.XINGTU_COMPLETED, RecordStatus.QUEUED_FOR_XINGTU) is False
    with pytest.raises(ValueError):
        assert_transition(RecordStatus.XINGTU_COMPLETED, RecordStatus.QUEUED_FOR_XINGTU)
