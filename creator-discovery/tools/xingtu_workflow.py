from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from pathlib import Path

from browser_runtime import BrowserRuntime, BrowserRuntimeConfig
from feishu_client import FeishuClient
from models import WorkflowSummary, XingtuRecord
from storage import LocalStorage
from utils import configure_logger, ensure_dir, env_flag, load_prompt

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover
    load_dotenv = None


@dataclass
class XingtuWorkflowConfig:
    mock_mode: bool = True
    limit: int = 20
    db_path: str = "data/cache/creator_discovery.db"
    log_dir: str = "data/logs"
    screenshot_dir: str = "data/screenshots"
    xingtu_url: str = "https://www.xingtu.cn"
    write_feishu: bool = False


class XingtuEnrichmentWorkflow:
    def __init__(self, config: XingtuWorkflowConfig) -> None:
        self.config = config
        ensure_dir(self.config.log_dir)
        ensure_dir(Path(self.config.db_path).parent)
        ensure_dir(self.config.screenshot_dir)

        self.logger = configure_logger("xingtu_workflow", self.config.log_dir)
        self.storage = LocalStorage(db_path=self.config.db_path, log_dir=self.config.log_dir)
        self.browser = BrowserRuntime(
            BrowserRuntimeConfig(
                mock_mode=self.config.mock_mode,
                screenshot_dir=Path(self.config.screenshot_dir),
            )
        )
        self.feishu = FeishuClient(log_dir=self.config.log_dir)

    def run(self) -> WorkflowSummary:
        summary = WorkflowSummary(workflow_name="xingtu_enrichment")
        checkpoint_key = "xingtu_enrichment:last_run"

        self.logger.info(
            "Start Xingtu enrichment workflow (mock_mode=%s, limit=%s)",
            self.config.mock_mode,
            self.config.limit,
        )

        try:
            pending_records = self.fetch_pending_creators()
            self.login_xingtu()

            for record in pending_records:
                summary.processed_count += 1
                xingtu_record = self.search_and_extract(record.creator_name)
                merged = self.storage.attach_xingtu_record(record.creator_name, xingtu_record)

                if xingtu_record.match_status == "complete":
                    summary.updated_count += 1
                else:
                    summary.skipped_count += 1

                if self.config.write_feishu:
                    self.feishu.update_xingtu_record(record.creator_name, merged.xingtu_record)  # type: ignore[arg-type]

                self.storage.save_checkpoint(
                    checkpoint_key,
                    {
                        "last_creator_name": record.creator_name,
                        "match_status": xingtu_record.match_status,
                        "processed_count": summary.processed_count,
                    },
                )
                summary.creator_names.append(record.creator_name)
                summary.checkpoints.append(checkpoint_key)

            summary.finish(status="completed")
        except Exception as exc:  # pragma: no cover
            summary.error_count += 1
            summary.notes.append(str(exc))
            summary.finish(status="failed")
            self.logger.exception("Xingtu enrichment workflow failed")
        finally:
            self.storage.save_workflow_summary(summary)

        self.logger.info("Xingtu enrichment workflow finished with status=%s", summary.status)
        return summary

    def login_xingtu(self) -> None:
        with self.browser.session("xingtu") as session:
            session.goto(self.config.xingtu_url)
            session.ensure_logged_in(expected_hint="进入达人搜索页面")
            self.logger.info("Xingtu page ready")

    def fetch_pending_creators(self):
        local_pending = self.storage.get_creators_missing_xingtu(limit=self.config.limit)
        if local_pending:
            self.logger.info("Loaded %s pending creators from local storage", len(local_pending))
            return local_pending

        if self.config.write_feishu:
            pending_from_feishu = self.feishu.read_pending_xingtu_records(limit=self.config.limit)
            self.logger.info("TODO: map Feishu pending records into CreatorRecord objects")
            self.logger.info("Feishu returned %s pending records", len(pending_from_feishu))

        return []

    def search_and_extract(self, creator_name: str) -> XingtuRecord:
        if self.config.mock_mode:
            return self._mock_xingtu_record(creator_name)

        prompt_text = load_prompt("xingtu_enrichment.md")
        self.logger.info("TODO: replace mock Xingtu extraction with live browser selectors")
        return XingtuRecord(match_status="partial", notes=[prompt_text[:80], f"TODO for {creator_name}"])

    def _mock_xingtu_record(self, creator_name: str) -> XingtuRecord:
        safe_name = creator_name.replace(" ", "")
        with self.browser.session("xingtu") as session:
            screenshot_path = session.capture_screenshot(f"xingtu_curve_{safe_name}")
        return XingtuRecord(
            xingtu_id=f"mock_{safe_name.lower()}",
            creator_types=["生活方式", "种草"],
            profile_url=f"https://www.xingtu.cn/mock/{safe_name}",
            price_20s=5000,
            price_20_to_60s=8000,
            price_60s_plus=12000,
            estimated_play_volume="50万+",
            sponsored_play_median="45万",
            organic_cpm="15",
            cpe="2.5",
            completion_rate="35%",
            play_curve_screenshot=screenshot_path,
            monthly_follower_growth_rate="5%",
            connected_user_fan_ratio="20%",
            deep_user_fan_ratio="8%",
            cooperative_clients=["品牌A", "品牌B"],
            match_status="complete",
            notes=[f"mock enrichment for {creator_name}"],
        )


def build_config(args: argparse.Namespace) -> XingtuWorkflowConfig:
    base_dir = Path(__file__).resolve().parents[1]
    return XingtuWorkflowConfig(
        mock_mode=args.mock,
        limit=args.limit,
        db_path=os.getenv("DISCOVERY_DB_PATH", str(base_dir / "data/cache/creator_discovery.db")),
        log_dir=os.getenv("DISCOVERY_LOG_DIR", str(base_dir / "data/logs")),
        screenshot_dir=os.getenv("DISCOVERY_SCREENSHOT_DIR", str(base_dir / "data/screenshots")),
        xingtu_url=os.getenv("XINGTU_HOME_URL", "https://www.xingtu.cn"),
        write_feishu=args.write_feishu,
    )


def main() -> None:
    if load_dotenv:
        load_dotenv(Path(__file__).resolve().parents[1] / ".env")

    parser = argparse.ArgumentParser(description="Run the Xingtu enrichment workflow skeleton")
    parser.add_argument("--mock", action="store_true", default=env_flag("DISCOVERY_MOCK_MODE", True))
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--write-feishu", action="store_true", default=False)
    args = parser.parse_args()

    workflow = XingtuEnrichmentWorkflow(build_config(args))
    summary = workflow.run()
    print(summary.to_dict())


if __name__ == "__main__":
    main()
