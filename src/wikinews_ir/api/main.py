"""ASGI entrypoint and application-owned backend lifecycle."""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from wikinews_ir.api.annotation_routes import router as annotation_router
from wikinews_ir.api.routes import router
from wikinews_ir.retrieval.engine import RetrievalEngine


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.engine = RetrievalEngine()
    try:
        yield
    finally:
        app.state.engine.close()


def create_app() -> FastAPI:
    app = FastAPI(title="Wikinews Search Engine", version="0.1.0", lifespan=lifespan)
    app.mount(
        "/static",
        StaticFiles(directory=str(Path(__file__).resolve().parent.parent / "web" / "static")),
        name="static",
    )
    app.include_router(router)
    app.include_router(annotation_router)

    @app.middleware("http")
    async def annotation_headers(request, call_next):
        response = await call_next(request)
        if (request.url.path.startswith("/api/annotation")
                and request.method in {"POST", "PUT", "PATCH", "DELETE"}
                and response.status_code >= 500):
            logging.getLogger("wikinews_ir.operations").error(
                "annotation_write_failed status=%s", response.status_code
            )
        if request.url.path.startswith("/api/annotation") or request.url.path in {
            "/annotate", "/coordinate"
        }:
            response.headers["Cache-Control"] = "no-store"
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["Referrer-Policy"] = "same-origin"
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; script-src 'self'; style-src 'self'; "
                "img-src 'self' data:; frame-ancestors 'none'; form-action 'self'; base-uri 'none'"
            )
        return response

    return app


app = create_app()
