from __future__ import annotations

import argparse
import asyncio
import json
import os
from pathlib import Path

from app.schemas.xingtu import XingtuFilterConfig, XingtuLiveRunConfig
from app.services.xingtu_runner import run_xingtu_live_flow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a minimal authenticated Xingtu creator-detail flow.")
    parser.add_argument("--config", help="Path to a JSON config file matching XingtuLiveRunConfig.")
    parser.add_argument("--storage-state", help="Path to Playwright storage state JSON.")
    parser.add_argument("--account-name", help="Optional workspace/account name shown on the Xingtu homepage.")
    parser.add_argument("--base-url", help="Optional Xingtu base URL override.")
    parser.add_argument("--filters-json", help="Inline JSON object for XingtuFilterConfig.")
    parser.add_argument("--filters-file", help="Path to a JSON file containing XingtuFilterConfig.")
    parser.add_argument("--row-limit", type=int, help="How many result rows to collect before opening detail.")
    parser.add_argument("--row-index", type=int, help="Which collected row to open for detail extraction.")
    parser.add_argument("--headed", action="store_true", help="Launch Chromium in headed mode.")
    return parser.parse_args()


def load_config(args: argparse.Namespace) -> XingtuLiveRunConfig:
    payload: dict[str, object] = {}

    if args.config:
        config_path = Path(args.config).expanduser().resolve()
        payload = json.loads(config_path.read_text(encoding="utf-8"))

    storage_state = args.storage_state or os.getenv("XINGTU_STORAGE_STATE")
    if storage_state:
        payload["storage_state_path"] = storage_state

    account_name = args.account_name or os.getenv("XINGTU_ACCOUNT_NAME")
    if account_name:
        payload["account_name"] = account_name

    base_url = args.base_url or os.getenv("XINGTU_BASE_URL")
    if base_url:
        payload["base_url"] = base_url

    if args.row_limit is not None:
        payload["row_limit"] = args.row_limit
    elif os.getenv("XINGTU_ROW_LIMIT"):
        payload["row_limit"] = int(os.getenv("XINGTU_ROW_LIMIT", "5"))

    if args.row_index is not None:
        payload["target_row_index"] = args.row_index
    elif os.getenv("XINGTU_ROW_INDEX"):
        payload["target_row_index"] = int(os.getenv("XINGTU_ROW_INDEX", "0"))

    if args.headed:
        payload["headless"] = False
    elif "headless" not in payload:
        payload["headless"] = os.getenv("XINGTU_HEADLESS", "true").lower() not in {"0", "false", "no"}

    filter_payload: dict[str, object] | None = None
    if args.filters_file:
        filter_payload = json.loads(Path(args.filters_file).expanduser().resolve().read_text(encoding="utf-8"))
    elif args.filters_json:
        filter_payload = json.loads(args.filters_json)
    elif os.getenv("XINGTU_FILTERS_JSON"):
        filter_payload = json.loads(os.getenv("XINGTU_FILTERS_JSON", "{}"))

    if filter_payload is not None:
        payload["filter_config"] = XingtuFilterConfig.model_validate(filter_payload)

    if "storage_state_path" not in payload:
        raise ValueError("A storage state path is required. Use --storage-state, --config, or XINGTU_STORAGE_STATE.")

    return XingtuLiveRunConfig.model_validate(payload)


async def _main() -> None:
    args = parse_args()
    config = load_config(args)
    result = await run_xingtu_live_flow(config)
    print(result.model_dump_json(indent=2, exclude_none=True))


if __name__ == "__main__":
    asyncio.run(_main())
