"""HTTP endpoints for the initial demo. No dump ingestion in API requests."""

from pathlib import Path

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from wikinews_ir.models import SearchResponse
from wikinews_ir.retrieval.engine import (
    RetrievalEngine,
    RetrievalUnavailable,
    SearchIndexMissing,
)
from wikinews_ir.retrieval.profiles import SUPPORTED_PROFILES

router = APIRouter()
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent.parent / "web" / "templates"))


def engine() -> RetrievalEngine:
    return RetrievalEngine()


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "index.html", {"profiles": SUPPORTED_PROFILES})


@router.get("/api/health")
def health():
    connected = engine().check_ready()
    if not connected:
        raise HTTPException(status_code=503, detail={"app": "ok", "elasticsearch": "unavailable"})
    return {"app": "ok", "elasticsearch": "ready"}


@router.get("/api/search", response_model=SearchResponse)
def search(
    q: str = Query(min_length=1, max_length=250),
    profile: str = "bm25",
    limit: int = Query(default=10, ge=1, le=100),
):
    if profile not in SUPPORTED_PROFILES:
        raise HTTPException(status_code=422, detail="Profilo non implementato")
    if not q.strip():
        raise HTTPException(status_code=422, detail="Query vuota")
    try:
        return engine().search(query=q, profile=profile, limit=limit)
    except SearchIndexMissing as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RetrievalUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
