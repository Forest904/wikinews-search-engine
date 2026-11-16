"""ASGI entrypoint and application-owned backend lifecycle."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

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
    return app


app = create_app()
