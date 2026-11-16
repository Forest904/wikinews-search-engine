"""ASGI entrypoint."""

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from wikinews_ir.api.routes import router

app = FastAPI(title="Wikinews Search Engine", version="0.1.0")
app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).resolve().parent.parent / "web" / "static")),
    name="static",
)
app.include_router(router)
