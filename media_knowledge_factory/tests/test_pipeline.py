from __future__ import annotations

import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline import MediaKnowledgeFactoryPipeline  # noqa: E402


INPUT_DIR = Path("/home/tuo/project/contact_db/outputs/file_transfer_assistant_cleaned/reconstructed_weflow")


def load_jsonl(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def test_pipeline_builds_required_assets(tmp_path: Path) -> None:
    output_dir = tmp_path / "seed_v1"
    pipeline = MediaKnowledgeFactoryPipeline(INPUT_DIR, output_dir)
    pipeline.run()

    required_files = [
        "conversation_messages.jsonl",
        "brief_cards.jsonl",
        "negotiation_episodes.jsonl",
        "talk_templates.jsonl",
        "workflow_playbook.jsonl",
        "retrieval_chunks.jsonl",
        "gold_episode_review_queue.jsonl",
        "tag_dictionary.yaml",
        "annotation_guideline.md",
        "asset_field_guide.md",
    ]
    for filename in required_files:
        assert (output_dir / filename).exists(), filename

    conversation_messages = load_jsonl(output_dir / "conversation_messages.jsonl")
    assert len(conversation_messages) == 533
    assert len({item["creator_id"] for item in conversation_messages}) == 5

    brief_cards = load_jsonl(output_dir / "brief_cards.jsonl")
    assert len(brief_cards) >= 5
    assert any(card["brand"] == "网易逆水寒" for card in brief_cards)

    episodes = load_jsonl(output_dir / "negotiation_episodes.jsonl")
    assert 15 <= len(episodes) <= 120
    assert any(len(item["message_ids"]) >= 3 for item in episodes)
    assert any(item["workflow_stage"] == "payment_push" for item in episodes)
    assert any(item["workflow_stage"] == "supplier_onboarding" for item in episodes)

    talk_templates = load_jsonl(output_dir / "talk_templates.jsonl")
    assert any(item["origin"] == "manual_seed" and item["workflow_stage"] == "cold_outreach" for item in talk_templates)
    assert any(item["origin"] == "manual_seed" and item["workflow_stage"] == "rebate_recovery" for item in talk_templates)

    retrieval_chunks = load_jsonl(output_dir / "retrieval_chunks.jsonl")
    assert {"turn_chunk", "episode_chunk", "template_chunk", "policy_chunk"} <= {
        item["chunk_type"] for item in retrieval_chunks
    }
    assert any("sft_bucket:negotiation" in item["filter_tags"] for item in retrieval_chunks if item["chunk_type"] == "turn_chunk")
    assert any(
        "objection_type:rebate_below_target" in item["filter_tags"]
        and "order_saturation:high" in item["filter_tags"]
        for item in retrieval_chunks
    )

    tag_dictionary = (output_dir / "tag_dictionary.yaml").read_text(encoding="utf-8")
    assert "workflow_stages:" in tag_dictionary
    assert "creator_traits:" in tag_dictionary

    annotation_guideline = (output_dir / "annotation_guideline.md").read_text(encoding="utf-8")
    assert "Episode 标注步骤" in annotation_guideline
    assert "SFT Bucket 归档" in annotation_guideline

    asset_field_guide = (output_dir / "asset_field_guide.md").read_text(encoding="utf-8")
    assert "```mermaid" in asset_field_guide
    assert "conversation_messages.jsonl" in asset_field_guide
    assert "annotation_guideline.md" in asset_field_guide
    assert "英文字段" in asset_field_guide

    gold_queue = load_jsonl(output_dir / "gold_episode_review_queue.jsonl")
    assert 50 <= len(gold_queue) <= 100
    assert all(item["review_status"] == "pending" for item in gold_queue)
