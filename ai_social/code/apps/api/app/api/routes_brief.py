from fastapi import APIRouter

from app.schemas.brief import BriefStructureRequest, BriefStructureResponse
from app.services.brief_structurer import structure_brief_from_input

router = APIRouter(prefix="/api/brief", tags=["brief"])


@router.post("/structure", response_model=BriefStructureResponse)
def structure_brief(request: BriefStructureRequest) -> BriefStructureResponse:
    brief, parser_notes = structure_brief_from_input(
        raw_text=request.raw_text,
        structured_draft=request.structured_draft,
    )
    return BriefStructureResponse(structured_brief=brief, parser_notes=parser_notes)
