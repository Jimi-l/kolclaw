from search_agent.adapters.xingtu.page import XingtuSearchCandidate, XingtuSearchOutcome
from search_agent.adapters.xingtu.workflow import XingtuEnrichmentWorkflow
from search_agent.enums import MatchConfidence, NextAction, RecordStatus
from search_agent.models.discovery import CreatorDiscoveryRecord
from search_agent.storage.jsonl_store import JsonlStore
from search_agent.storage.queue import XingtuQueueStore
from search_agent.tests.test_matching import make_discovery_record


def test_choose_best_candidate_accepts_single_exact_name_match() -> None:
    record = make_discovery_record()
    outcome = XingtuSearchOutcome(
        query=record.creator_name or "",
        result_kind="matched_candidates",
        candidates=[
            XingtuSearchCandidate(
                candidate_name=record.creator_name,
                candidate_follower_hint=None,
                candidate_avatar_hint=None,
                candidate_creator_type=None,
                candidate_content_hint=None,
                candidate_url="https://www.xingtu.cn/creator/example",
            ),
            XingtuSearchCandidate(
                candidate_name="其他达人",
                candidate_follower_hint="200万粉丝",
                candidate_avatar_hint=None,
                candidate_creator_type="影视娱乐",
                candidate_content_hint="影视娱乐",
                candidate_url="https://www.xingtu.cn/creator/other",
            ),
        ],
    )

    candidate, decision = XingtuEnrichmentWorkflow._choose_best_candidate(None, record, outcome)

    assert candidate is outcome.candidates[0]
    assert decision.match_confidence == MatchConfidence.HIGH


def test_choose_best_candidate_rejects_results_without_exact_name_match() -> None:
    record = make_discovery_record()
    payload = record.model_dump(mode="json")
    payload["creator_name"] = "Jue李珏"
    record = CreatorDiscoveryRecord.model_validate(payload)
    outcome = XingtuSearchOutcome(
        query="Jue李珏",
        result_kind="matched_candidates",
        candidates=[
            XingtuSearchCandidate(
                candidate_name="施施S.jue",
                candidate_follower_hint="60w",
                candidate_avatar_hint=None,
                candidate_creator_type="生活",
                candidate_content_hint="夫妻情感 家庭生活记录",
                candidate_url="https://www.xingtu.cn/creator/jue1",
            ),
            XingtuSearchCandidate(
                candidate_name="Jue生活",
                candidate_follower_hint="20w",
                candidate_avatar_hint=None,
                candidate_creator_type="生活",
                candidate_content_hint="生活",
                candidate_url="https://www.xingtu.cn/creator/jue2",
            ),
        ],
    )

    candidate, decision = XingtuEnrichmentWorkflow._choose_best_candidate(None, record, outcome)

    assert candidate is None
    assert decision is None
    assert XingtuEnrichmentWorkflow._exact_name_match_count(record, outcome) == 0


def test_choose_best_candidate_accepts_unique_exact_among_many_results() -> None:
    record = make_discovery_record()
    payload = record.model_dump(mode="json")
    payload["creator_name"] = "影视飓风"
    record = CreatorDiscoveryRecord.model_validate(payload)
    outcome = XingtuSearchOutcome(
        query="影视飓风",
        result_kind="matched_candidates",
        candidates=[
            XingtuSearchCandidate(
                candidate_name="影视飓风",
                candidate_follower_hint="1410.3w",
                candidate_avatar_hint=None,
                candidate_creator_type="科技数码",
                candidate_content_hint="数码周边 科技数码",
                candidate_url="https://www.xingtu.cn/creator/exact",
            ),
            XingtuSearchCandidate(
                candidate_name="影视飓风剪辑",
                candidate_follower_hint="10w",
                candidate_avatar_hint=None,
                candidate_creator_type="影视",
                candidate_content_hint="影视",
                candidate_url="https://www.xingtu.cn/creator/other",
            ),
        ],
    )

    candidate, decision = XingtuEnrichmentWorkflow._choose_best_candidate(None, record, outcome)

    assert candidate is outcome.candidates[0]
    assert decision.match_confidence == MatchConfidence.HIGH


def test_search_with_fallback_only_searches_original_creator_name() -> None:
    class _Adapter:
        def __init__(self) -> None:
            self.queries = []

        def search(self, query: str) -> XingtuSearchOutcome:
            self.queries.append(query)
            return XingtuSearchOutcome(query=query, result_kind="not_found")

    record = make_discovery_record()
    payload = record.model_dump(mode="json")
    payload["creator_name"] = "BB大王"
    record = CreatorDiscoveryRecord.model_validate(payload)
    adapter = _Adapter()

    outcome = XingtuEnrichmentWorkflow._search_with_fallback(None, adapter, record)

    assert adapter.queries == ["BB大王"]
    assert outcome.query == "BB大王"


def test_backfill_queue_from_discovery_records(tmp_path) -> None:
    queued_record = make_discovery_record()
    discovery_payload = queued_record.model_dump(mode="json")
    discovery_payload.update(
        {
            "status": RecordStatus.DISCOVERED.value,
            "next_action": NextAction.CONTINUE.value,
        }
    )
    discovery_record = CreatorDiscoveryRecord.model_validate(discovery_payload)
    discovery_output = tmp_path / "discovery_records.jsonl"
    queue_output = tmp_path / "xingtu_queue.jsonl"
    JsonlStore(discovery_output, CreatorDiscoveryRecord).append(discovery_record)

    workflow = XingtuEnrichmentWorkflow.__new__(XingtuEnrichmentWorkflow)
    workflow.paths = type("Paths", (), {"discovery_output": discovery_output, "queue_output": queue_output})()
    workflow.queue_store = XingtuQueueStore(queue_output)
    workflow.logger = type("Logger", (), {"info": lambda *args, **kwargs: None})()

    assert workflow._backfill_queue_from_discovery(processed_record_ids=set()) == 1

    queued_records = XingtuQueueStore(queue_output).load_pending()
    assert len(queued_records) == 1
    assert queued_records[0].record_id == discovery_record.record_id
    assert queued_records[0].status == RecordStatus.QUEUED_FOR_XINGTU
    assert queued_records[0].next_action == NextAction.QUEUE_FOR_XINGTU
