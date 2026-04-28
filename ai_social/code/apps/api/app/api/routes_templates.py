from fastapi import APIRouter

from app.services.strategy_loader import StrategyLoader

router = APIRouter(tags=["templates"])
loader = StrategyLoader()


@router.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/api/templates")
def list_templates():
    return loader.list_templates()
