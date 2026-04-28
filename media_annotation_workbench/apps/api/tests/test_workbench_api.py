from __future__ import annotations

import sys
from pathlib import Path

from fastapi.testclient import TestClient


API_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(API_ROOT))

from main import create_app  # noqa: E402
from app.core.config import Settings  # noqa: E402


SEED_DIR = Path("/home/tuo/project/media_knowledge_factory/outputs/seed_v1")


def login(client: TestClient, username: str, password: str) -> str:
    response = client.post(
        "/api/auth/login",
        json={"username": username, "password": password},
    )
    assert response.status_code == 200, response.text
    assert "role_label" in response.json()["user"]
    return response.json()["access_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_workbench_import_review_and_permissions(tmp_path: Path) -> None:
    database_url = f"sqlite:///{tmp_path / 'workbench.db'}"
    app = create_app(Settings(database_url=database_url, secret_key="test-secret"))

    with TestClient(app) as client:
        admin_token = login(client, "admin", "admin123")
        viewer_token = login(client, "viewer", "viewer123")

        import_response = client.post(
            "/api/imports",
            headers=auth_headers(admin_token),
            json={"source_dir": str(SEED_DIR), "activate": True},
        )
        assert import_response.status_code == 200, import_response.text
        snapshot = import_response.json()["snapshot"]
        assert snapshot["asset_counts"]["conversation_messages"] == 533
        assert snapshot["asset_counts"]["gold_episode_review_queue"] == 78

        dashboard_response = client.get("/api/dashboard/summary", headers=auth_headers(admin_token))
        assert dashboard_response.status_code == 200, dashboard_response.text
        dashboard = dashboard_response.json()
        assert dashboard["asset_counts"]["brief_cards"] == 7
        assert dashboard["review_counts"]["pending"] == 78
        assert any(card["label"] == "Brief 知识卡" and card["count"] == 7 for card in dashboard["asset_count_cards"])
        assert any(card["label"] == "待审核" and card["count"] == 78 for card in dashboard["review_status_cards"])
        assert all("label" in card for card in dashboard["stage_distribution_cards"])

        review_list_response = client.get("/api/reviews/tasks", headers=auth_headers(admin_token))
        assert review_list_response.status_code == 200, review_list_response.text
        review_list = review_list_response.json()
        assert review_list["total"] == 78
        first_task = review_list["items"][0]
        assert first_task["status_label"] == "待审核"
        assert "workflow_stage_label" in first_task

        review_detail_response = client.get(
            f"/api/reviews/tasks/{first_task['review_task_id']}",
            headers=auth_headers(admin_token),
        )
        assert review_detail_response.status_code == 200, review_detail_response.text
        review_detail = review_detail_response.json()
        assert review_detail["raw_episode"] is not None
        assert len(review_detail["evidence_messages"]) >= 1
        assert len(review_detail["evidence_chat_messages"]) >= 1
        first_message = review_detail["evidence_chat_messages"][0]
        assert "role_label" in first_message
        assert "speaker_name" in first_message
        assert "formatted_time" in first_message
        assert "clean_text" in first_message
        assert "raw_text" in first_message
        direct_ids = set(review_detail["raw_episode"]["evidence_message_ids"])
        assert any(message["is_direct_evidence"] for message in review_detail["evidence_chat_messages"])
        assert all(
            message["is_direct_evidence"] == (message["message_id"] in direct_ids)
            for message in review_detail["evidence_chat_messages"]
        )

        viewer_draft_response = client.post(
            f"/api/reviews/tasks/{first_task['review_task_id']}/draft",
            headers=auth_headers(viewer_token),
            json={"workflow_stage": "price_negotiation"},
        )
        assert viewer_draft_response.status_code == 403

        claim_response = client.post(
            f"/api/reviews/tasks/{first_task['review_task_id']}/claim",
            headers=auth_headers(admin_token),
        )
        assert claim_response.status_code == 200, claim_response.text

        draft_response = client.post(
            f"/api/reviews/tasks/{first_task['review_task_id']}/draft",
            headers=auth_headers(admin_token),
            json={
                "workflow_stage": "price_negotiation",
                "episode_goal": "cut_price",
                "objection_type": "price_too_high",
                "outcome": "advanced",
                "confidence": 0.91,
                "review_notes": "人工确认该片段更接近砍价语境。",
                "creator_traits": [
                    {
                        "trait_name": "interaction_style",
                        "value": "direct",
                        "confidence": 0.93,
                        "evidence_message_ids": review_detail["raw_episode"]["evidence_message_ids"],
                        "rationale": "人工审核后判断达人回复更直接。",
                    }
                ],
            },
        )
        assert draft_response.status_code == 200, draft_response.text

        episode_id = first_task["episode_id"]
        asset_detail_response = client.get(
            f"/api/assets/negotiation_episodes/{episode_id}?view=reviewed&snapshot_id={snapshot['snapshot_id']}",
            headers=auth_headers(admin_token),
        )
        assert asset_detail_response.status_code == 200, asset_detail_response.text
        episode_detail = asset_detail_response.json()
        assert episode_detail["raw_item"]["workflow_stage"] != "price_negotiation"
        assert episode_detail["reviewed_item"]["workflow_stage"] == "price_negotiation"
        assert episode_detail["reviewed_item"]["review_status"] == "in_progress"

        export_response = client.get(
            f"/api/exports/reviewed-episodes?snapshot_id={snapshot['snapshot_id']}",
            headers=auth_headers(admin_token),
        )
        assert export_response.status_code == 200, export_response.text
        export_payload = export_response.json()
        exported_episode = next(item for item in export_payload["items"] if item["episode_id"] == episode_id)
        assert exported_episode["workflow_stage"] == "price_negotiation"
        assert exported_episode["review_status"] == "in_progress"

        approve_response = client.post(
            f"/api/reviews/tasks/{first_task['review_task_id']}/approve",
            headers=auth_headers(admin_token),
            json={"review_notes": "确认通过。"},
        )
        assert approve_response.status_code == 200, approve_response.text
        assert approve_response.json()["task"]["status"] == "approved"
