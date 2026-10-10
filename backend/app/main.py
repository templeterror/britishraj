from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.heirloom.config import HeirloomSettings, get_settings
from app.heirloom.envelope import Meta, install_error_handlers, ok

API_PREFIX = "/api/v1"


def create_app(settings: HeirloomSettings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(title="Heirloom Relay")
    app.state.settings = settings

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

    app.include_router(api)
    return app


app = create_app()
