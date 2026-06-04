from types import SimpleNamespace

from search_agent.adapters.douyin.workflow import CreatorDiscoveryWorkflow
from search_agent.enums import NextAction, RecordStatus
from search_agent.tests.test_matching import make_discovery_record


class _FakeLogger:
    def info(self, *args, **kwargs) -> None:
        return None


class _FakeQueueStore:
    def __init__(self) -> None:
        self.records = []

    def enqueue(self, record) -> None:
        self.records.append(record)


def _workflow_with_fake_queue() -> tuple[CreatorDiscoveryWorkflow, _FakeQueueStore]:
    workflow = CreatorDiscoveryWorkflow.__new__(CreatorDiscoveryWorkflow)
    queue_store = _FakeQueueStore()
    workflow.queue_store = queue_store
    workflow.paths = SimpleNamespace(queue_output="runtime/queues/xingtu_queue.jsonl")
    workflow.logger = _FakeLogger()
    return workflow, queue_store


def test_discovery_record_is_copied_into_xingtu_queue_with_queue_status() -> None:
    workflow, queue_store = _workflow_with_fake_queue()
    queued_record = make_discovery_record()
    discovery_payload = queued_record.model_dump(mode="json")
    discovery_payload.update(
        {
            "status": RecordStatus.DISCOVERED.value,
            "next_action": NextAction.CONTINUE.value,
        }
    )
    discovery_record = queued_record.model_validate(discovery_payload)

    assert workflow._enqueue_record_for_xingtu(discovery_record) is True

    assert len(queue_store.records) == 1
    assert queue_store.records[0].record_id == discovery_record.record_id
    assert queue_store.records[0].status == RecordStatus.QUEUED_FOR_XINGTU
    assert queue_store.records[0].next_action == NextAction.QUEUE_FOR_XINGTU
    assert discovery_record.status == RecordStatus.DISCOVERED
    assert discovery_record.next_action == NextAction.CONTINUE


def test_incomplete_discovery_record_is_not_queued_for_xingtu() -> None:
    workflow, queue_store = _workflow_with_fake_queue()
    queued_record = make_discovery_record()
    discovery_payload = queued_record.model_dump(mode="json")
    discovery_payload.update(
        {
            "status": RecordStatus.DISCOVERED.value,
            "next_action": NextAction.CONTINUE.value,
            "follower_count_raw": None,
        }
    )
    discovery_record = queued_record.model_validate(discovery_payload)

    assert workflow._enqueue_record_for_xingtu(discovery_record) is False
    assert queue_store.records == []
