from __future__ import annotations

from fastapi import APIRouter

from app.schemas.reference_docs import ExternalDocReferenceResponse
from app.schemas.shortlist import (
    ShortlistParseRequest,
    ShortlistParseResponse,
    ShortlistPlanRequest,
    ShortlistPlanResponse,
    ShortlistRunRequest,
    ShortlistRunResponse,
)
from app.services.reference_docs_loader import ReferenceDocsLoader
from app.services.shortlist_runner import ShortlistRunner

router = APIRouter(prefix="/api/shortlist", tags=["shortlist"])
reference_loader = ReferenceDocsLoader()
shortlist_runner = ShortlistRunner(reference_loader=reference_loader)


@router.get("/references", response_model=ExternalDocReferenceResponse)
def shortlist_references() -> ExternalDocReferenceResponse:
    return ExternalDocReferenceResponse(references=reference_loader.list_v1_operational_references())


@router.post("/parse", response_model=ShortlistParseResponse)
def parse_shortlist_brief(request: ShortlistParseRequest) -> ShortlistParseResponse:
    requirement, parser_notes = shortlist_runner.parse_requirement(
        raw_text=request.raw_text,
        structured_requirement=request.structured_requirement,
    )
    return ShortlistParseResponse(
        structured_requirement=requirement,
        parser_notes=parser_notes,
    )


@router.post("/plan", response_model=ShortlistPlanResponse)
def shortlist_plan(request: ShortlistPlanRequest) -> ShortlistPlanResponse:
    return shortlist_runner.preview_plan(request)


@router.post("/run", response_model=ShortlistRunResponse)
async def run_shortlist(request: ShortlistRunRequest) -> ShortlistRunResponse:
    return await shortlist_runner.run(request)
