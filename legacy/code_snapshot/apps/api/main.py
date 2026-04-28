from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_brief import router as brief_router
from app.api.routes_candidates import router as candidates_router
from app.api.routes_templates import router as templates_router
from app.core.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.api_title,
    version="0.1.0",
    description="KOLClaw demo API backed by local JSON data.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(templates_router)
app.include_router(brief_router)
app.include_router(candidates_router)
