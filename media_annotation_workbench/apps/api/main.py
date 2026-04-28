from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes_assets import router as assets_router
from app.api.routes_auth import router as auth_router
from app.api.routes_dashboard import router as dashboard_router
from app.api.routes_docs import router as docs_router
from app.api.routes_exports import router as exports_router
from app.api.routes_imports import router as imports_router
from app.api.routes_reviews import router as reviews_router
from app.api.routes_snapshots import router as snapshots_router
from app.core.config import Settings, get_settings
from app.core.database import init_db, make_engine
from app.services.seed import seed_local_users


def create_app(settings: Settings | None = None) -> FastAPI:
    resolved_settings = settings or get_settings()
    engine = make_engine(resolved_settings.database_url)

    from sqlalchemy.orm import sessionmaker

    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        init_db(engine)
        session = session_factory()
        try:
            seed_local_users(session, resolved_settings)
            session.commit()
        finally:
            session.close()
        yield

    app = FastAPI(
        title=resolved_settings.api_title,
        version="0.1.0",
        description="Internal knowledge database and annotation workbench for AI media operations.",
        lifespan=lifespan,
    )

    app.state.settings = resolved_settings
    app.state.session_factory = session_factory
    app.state.engine = engine

    app.add_middleware(
        CORSMiddleware,
        allow_origins=resolved_settings.api_cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(auth_router)
    app.include_router(dashboard_router)
    app.include_router(imports_router)
    app.include_router(snapshots_router)
    app.include_router(assets_router)
    app.include_router(reviews_router)
    app.include_router(docs_router)
    app.include_router(exports_router)
    return app


app = create_app()
