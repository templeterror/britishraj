from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select

from app.heirloom.config import HeirloomSettings, get_settings
from app.heirloom.db import SessionFactory, init_db, make_engine
from app.heirloom.envelope import Meta, install_error_handlers, ok
from app.heirloom.models import Family
from app.heirloom.routers import decisions, demo, families, graph, intents
from app.heirloom.services import graph as graph_service
from app.heirloom.services.seed import reset_and_seed

API_PREFIX = "/api/v1"


def create_app(settings: HeirloomSettings | None = None) -> FastAPI:
    settings = settings or get_settings()
    engine = make_engine(settings.database_url)
    graph_service.register_handlers()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        init_db(engine)
        if settings.mode == "demo":
            with SessionFactory(bind=engine) as session:
                if session.scalar(select(Family.id).limit(1)) is None:
                    reset_and_seed(session)
        yield
        engine.dispose()

    app = FastAPI(title="Heirloom Relay", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_origin],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["Authorization", "Content-Type"],
    )

    @app.middleware("http")
    async def no_store(request: Request, call_next):
        response = await call_next(request)
        if request.url.path.startswith(API_PREFIX):
            response.headers["Cache-Control"] = "no-store"
        return response

    install_error_handlers(app)

    api = APIRouter(prefix=API_PREFIX)

    @api.get("/health")
    def health(request: Request) -> dict:
        return ok({"status": "ok"}, Meta(mode=request.app.state.settings.mode))

    api.include_router(demo.router)
    api.include_router(families.router)
    api.include_router(graph.router)
    api.include_router(intents.router)
    api.include_router(decisions.router)
    app.include_router(api)
    return app


app = create_app()
