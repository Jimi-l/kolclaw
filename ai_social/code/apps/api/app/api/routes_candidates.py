from __future__ import annotations

import json

from fastapi import APIRouter

from app.core.config import get_settings
from app.schemas.brief import CampaignBrief
from app.schemas.pipeline import CandidateRunRequest, CandidatesRunResponse, RetrievalPlan, RetrievalPlanRequest
from app.services.pipeline_runner import PipelineRunner
from app.services.retrieval_planner import build_retrieval_plan

router = APIRouter(tags=["candidates"])
settings = get_settings()
runner = PipelineRunner()


@router.post("/api/retrieval/plan", response_model=RetrievalPlan)
def retrieval_plan(request: RetrievalPlanRequest) -> RetrievalPlan:
    template = runner.resolve_template(template_id=request.template_id, template=request.template)
    return build_retrieval_plan(brief=request.brief, template=template)


@router.post("/api/candidates/run", response_model=CandidatesRunResponse)
def run_candidates(request: CandidateRunRequest) -> CandidatesRunResponse:
    return runner.run(
        brief=request.brief,
        template_id=request.template_id,
        template=request.template,
        limit=request.limit,
    )


@router.get("/api/candidates/sample", response_model=CandidatesRunResponse)
def sample_candidates() -> CandidatesRunResponse:
    with (settings.mock_briefs_dir / "fashion_offline_event.json").open("r", encoding="utf-8") as file:
        brief = CampaignBrief.model_validate(json.load(file))
    return runner.run(brief=brief, template_id="fashion_event_default", limit=10)
