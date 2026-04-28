from __future__ import annotations

from pathlib import Path

from app.core.config import get_settings
from app.schemas.shortlist import (
    ShortlistPlanRequest,
    ShortlistPlanResponse,
    ShortlistRequirement,
    ShortlistRunMetadata,
    ShortlistRunRequest,
    ShortlistRunResponse,
)
from app.schemas.xingtu import XingtuCreatorDetail, XingtuLiveRunConfig
from app.services.reference_docs_loader import ReferenceDocsLoader
from app.services.shortlist_brief_parser import structure_shortlist_requirement
from app.services.shortlist_scoring import rank_shortlist_candidates
from app.services.shortlist_search_planner import build_shortlist_search_plan
from app.services.xingtu_selectors import XingtuResultSelectors
from app.services.xingtu_workflow import (
    apply_filters,
    collect_creator_detail,
    collect_current_page_rows,
    dismiss_non_blocking_popups,
    open_creator_detail,
    open_creator_search,
    open_workspace,
)


class ShortlistRunner:
    """Runs the V1 shortlist pipeline on top of the working Xingtu live flow."""

    def __init__(self, reference_loader: ReferenceDocsLoader | None = None) -> None:
        self.settings = get_settings()
        self.reference_loader = reference_loader or ReferenceDocsLoader()

    def parse_requirement(
        self,
        raw_text: str | None,
        structured_requirement: ShortlistRequirement | None,
    ) -> tuple[ShortlistRequirement, list[str]]:
        return structure_shortlist_requirement(
            raw_text=raw_text,
            structured_requirement=structured_requirement,
        )

    def preview_plan(self, request: ShortlistPlanRequest) -> ShortlistPlanResponse:
        requirement, parser_notes = self.parse_requirement(
            raw_text=request.raw_text,
            structured_requirement=request.structured_requirement,
        )
        search_plan = build_shortlist_search_plan(
            requirement=requirement,
            collection_limit=request.collection_limit,
            shortlist_limit=request.shortlist_limit,
        )
        return ShortlistPlanResponse(
            structured_requirement=requirement,
            parser_notes=parser_notes,
            search_plan=search_plan,
            reference_docs=self.reference_loader.list_v1_operational_references(),
        )

    async def run(self, request: ShortlistRunRequest) -> ShortlistRunResponse:
        requirement, parser_notes = self.parse_requirement(
            raw_text=request.raw_text,
            structured_requirement=request.structured_requirement,
        )
        search_plan = build_shortlist_search_plan(
            requirement=requirement,
            collection_limit=request.collection_limit,
            shortlist_limit=request.shortlist_limit,
        )

        collection = await self._collect_creators(
            request=request,
            search_plan=search_plan,
        )
        shortlist, filtered_out_reasons = rank_shortlist_candidates(
            requirement=requirement,
            creators=collection["collected_creators"],
            shortlist_limit=search_plan.shortlist_limit,
        )

        metadata = ShortlistRunMetadata(
            storage_state_path=collection["storage_state_path"],
            account_name=request.account_name,
            homepage_url=collection["homepage_url"],
            creator_search_url=collection["creator_search_url"],
            rows_seen=collection["rows_seen"],
            creators_collected=len(collection["collected_creators"]),
            creators_ranked=len(shortlist),
            creators_filtered_out=max(len(collection["collected_creators"]) - len(shortlist), 0),
            filtered_out_reasons=filtered_out_reasons,
            collection_errors=collection["collection_errors"],
        )

        return ShortlistRunResponse(
            raw_brief=request.raw_text,
            structured_requirement=requirement,
            parser_notes=parser_notes,
            search_plan=search_plan,
            collected_creators=collection["collected_creators"],
            shortlist=shortlist,
            reference_docs=self.reference_loader.list_v1_operational_references(),
            metadata=metadata,
            debug={
                "preview_rows": [row.model_dump(exclude_none=True) for row in collection["preview_rows"]],
            },
        )

    async def _collect_creators(self, request: ShortlistRunRequest, search_plan) -> dict[str, object]:
        storage_state_path = self.settings.resolve_storage_state_path(request.storage_state_path)
        if not storage_state_path.exists():
            raise FileNotFoundError(f"Storage state file not found: {storage_state_path}")

        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Python Playwright is not installed. Install it with `pip install playwright` "
                "and run `playwright install chromium` before using the shortlist runner."
            ) from exc

        collected_creators: list[XingtuCreatorDetail] = []
        collection_errors: list[str] = []
        preview_rows = []
        homepage_url = ""
        creator_search_url = ""

        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=request.headless)
            context = await browser.new_context(storage_state=str(storage_state_path))
            page = await context.new_page()

            try:
                await open_workspace(page, account_name=request.account_name, base_url=request.base_url)
                homepage_url = page.url

                await open_creator_search(page)
                await apply_filters(page, search_plan.filter_config)
                creator_search_url = page.url

                preview_rows = await collect_current_page_rows(page, row_limit=search_plan.collection_limit)
                for row_index in range(len(preview_rows)):
                    detail_page = None
                    try:
                        detail_page = await open_creator_detail(page, row_index)
                        detail = await collect_creator_detail(detail_page)
                        collected_creators.append(detail)
                    except Exception as exc:
                        collection_errors.append(f"row_{row_index}: {exc}")
                    finally:
                        if detail_page is not None:
                            await _restore_search_surface(page, detail_page)
            finally:
                await context.close()
                await browser.close()

        return {
            "storage_state_path": str(storage_state_path),
            "homepage_url": homepage_url,
            "creator_search_url": creator_search_url,
            "rows_seen": len(preview_rows),
            "preview_rows": preview_rows,
            "collected_creators": collected_creators,
            "collection_errors": collection_errors,
        }


async def _restore_search_surface(search_page, detail_page) -> None:
    if detail_page is search_page:
        try:
            await search_page.go_back()
            await search_page.wait_for_load_state("domcontentloaded")
        except Exception:
            pass
    else:
        try:
            await detail_page.close()
        except Exception:
            pass
        try:
            await search_page.bring_to_front()
        except Exception:
            pass

    try:
        await dismiss_non_blocking_popups(search_page)
        await search_page.locator(XingtuResultSelectors.CONTENT_ROOT).first.wait_for(state="visible", timeout=3000)
    except Exception:
        try:
            await search_page.wait_for_timeout(500)
        except Exception:
            return
