from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Optional

from models import CreatorRecord, XingtuRecord
from utils import configure_logger, env_flag


@dataclass
class FeishuConfig:
    base_app_token: Optional[str] = None
    table_id: Optional[str] = None
    mock_mode: bool = True


class FeishuClient:
    def __init__(self, config: Optional[FeishuConfig] = None, log_dir: str = "data/logs") -> None:
        self.config = config or FeishuConfig(
            base_app_token=os.getenv("FEISHU_BASE_APP_TOKEN"),
            table_id=os.getenv("FEISHU_TABLE_ID"),
            mock_mode=env_flag("FEISHU_MOCK_MODE", True),
        )
        self.logger = configure_logger("feishu_client", log_dir)

    def read_pending_xingtu_records(self, limit: int = 20) -> list[dict[str, Any]]:
        self.logger.info("Read pending Xingtu records from Feishu (limit=%s)", limit)
        if self.config.mock_mode:
            return []
        raise NotImplementedError("TODO: implement real Feishu read for pending Xingtu records")

    def upsert_creator_record(self, record: CreatorRecord) -> dict[str, Any]:
        self.logger.info("Upsert creator record to Feishu: %s", record.creator_name)
        if self.config.mock_mode:
            return {"status": "mocked", "record_id": record.record_id}
        raise NotImplementedError("TODO: implement real Feishu creator upsert")

    def update_xingtu_record(self, creator_name: str, xingtu_record: XingtuRecord) -> dict[str, Any]:
        self.logger.info("Update Xingtu fields in Feishu: %s", creator_name)
        if self.config.mock_mode:
            return {"status": "mocked", "creator_name": creator_name, "match_status": xingtu_record.match_status}
        raise NotImplementedError("TODO: implement real Feishu Xingtu update")
