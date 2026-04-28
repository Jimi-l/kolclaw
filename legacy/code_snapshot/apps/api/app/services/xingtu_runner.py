from __future__ import annotations

from pathlib import Path

from app.schemas.xingtu import XingtuLiveRunConfig, XingtuLiveRunResult
from app.services.xingtu_workflow import (
    apply_filters,
    collect_creator_detail,
    collect_current_page_rows,
    open_creator_detail,
    open_creator_search,
    open_workspace,
    validate_creator_detail,
)


async def run_xingtu_live_flow(config: XingtuLiveRunConfig) -> XingtuLiveRunResult:
    """Run a minimal authenticated Xingtu creator-search flow and return structured detail."""

    storage_state_path = Path(config.storage_state_path).expanduser().resolve()
    if not storage_state_path.exists():
        raise FileNotFoundError(f"Storage state file not found: {storage_state_path}")

    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError(
            "Python Playwright is not installed. Install it with `pip install playwright` "
            "and run `playwright install chromium` before using the live Xingtu runner."
        ) from exc

    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=config.headless)
        context = await browser.new_context(storage_state=str(storage_state_path))
        page = await context.new_page()

        try:
            await open_workspace(
                page,
                account_name=config.account_name,
                base_url=config.base_url,
            )
            homepage_url = page.url

            await open_creator_search(page)
            await apply_filters(page, config.filter_config)
            creator_search_url = page.url

            rows = await collect_current_page_rows(page, row_limit=config.row_limit)
            if not rows:
                raise RuntimeError("No creator rows were found after applying the requested filters.")
            if config.target_row_index >= len(rows):
                raise IndexError(
                    f"Requested row index {config.target_row_index} but only {len(rows)} rows were collected."
                )

            selected_row = rows[config.target_row_index]
            detail_page = await open_creator_detail(page, config.target_row_index)
            detail = await collect_creator_detail(detail_page)
            missing_required_fields = validate_creator_detail(detail)

            return XingtuLiveRunResult(
                storage_state_path=str(storage_state_path),
                homepage_url=homepage_url,
                creator_search_url=creator_search_url,
                rows_collected=len(rows),
                selected_row=selected_row,
                detail=detail,
                missing_required_fields=missing_required_fields,
            )
        finally:
            await context.close()
            await browser.close()
