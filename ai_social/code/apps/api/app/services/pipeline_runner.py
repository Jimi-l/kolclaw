from __future__ import annotations

from app.schemas.brief import CampaignBrief
from app.schemas.pipeline import CandidatesRunResponse, PipelineMetadata
from app.schemas.strategy_template import StrategyTemplate
from app.services.candidate_repository import CandidateRepository
from app.services.ranking_engine import rank_candidates
from app.services.retrieval_planner import build_retrieval_plan
from app.services.strategy_loader import StrategyLoader


class PipelineRunner:
    """Coordinates template resolution, retrieval planning, and ranking."""

    def __init__(
        self,
        strategy_loader: StrategyLoader | None = None,
        candidate_repository: CandidateRepository | None = None,
    ) -> None:
        self.strategy_loader = strategy_loader or StrategyLoader()
        self.candidate_repository = candidate_repository or CandidateRepository()

    def resolve_template(self, template_id: str | None, template: StrategyTemplate | None) -> StrategyTemplate:
        if template is not None:
            return template
        if template_id is None:
            raise ValueError("template_id or template must be provided.")
        return self.strategy_loader.get_template(template_id)

    def run(
        self,
        brief: CampaignBrief,
        template_id: str | None = None,
        template: StrategyTemplate | None = None,
        limit: int = 20,
    ) -> CandidatesRunResponse:
        resolved_template = self.resolve_template(template_id=template_id, template=template)
        retrieval_plan = build_retrieval_plan(brief=brief, template=resolved_template)
        candidates = self.candidate_repository.list_candidates()
        ranked_candidates, filter_reasons, passed_count = rank_candidates(
            candidates=candidates,
            brief=brief,
            template=resolved_template,
            limit=limit,
        )
        metadata = PipelineMetadata(
            template_id=resolved_template.template_id,
            total_candidates_loaded=len(candidates),
            candidates_after_filters=passed_count,
            filtered_out=len(candidates) - passed_count,
            filter_reasons=filter_reasons,
        )
        return CandidatesRunResponse(
            brief=brief,
            template=resolved_template,
            retrieval_plan=retrieval_plan,
            candidates=ranked_candidates,
            metadata=metadata,
        )
