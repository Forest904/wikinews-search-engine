"""HTTP endpoints for the initial demo. No dump ingestion in API requests."""

from pathlib import Path
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from wikinews_ir.models import Article, SearchRequest, SearchResponse
from wikinews_ir.retrieval.engine import (
    ArticleNotFound,
    RetrievalEngine,
    RetrievalUnavailable,
    SearchIndexMissing,
)
from wikinews_ir.retrieval.profiles import SUPPORTED_PROFILES

router = APIRouter()
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "web" / "templates")
)


def engine(request: Request) -> RetrievalEngine:
    return request.app.state.engine


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "index.html", {"profiles": SUPPORTED_PROFILES})


@router.get("/api/health")
def health(backend: RetrievalEngine = Depends(engine)):
    connected = backend.check_ready()
    if not connected:
        raise HTTPException(status_code=503, detail={"app": "ok", "elasticsearch": "unavailable"})
    return {"app": "ok", "elasticsearch": "ready"}


@router.get("/api/search", response_model=SearchResponse)
def search(
    backend: RetrievalEngine = Depends(engine),
    q: str = Query(),
    profile: str = "bm25",
    limit: int = Query(default=10, ge=1, le=100),
):
    try:
        search_request = SearchRequest(query=q, profile=profile, limit=limit)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="Parametri di ricerca non validi") from exc
    try:
        return backend.search(search_request)
    except SearchIndexMissing as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RetrievalUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/api/articles/{document_id}", response_model=Article)
def article(document_id: str, backend: RetrievalEngine = Depends(engine)):
    try:
        return backend.get_article(document_id)
    except (ArticleNotFound, SearchIndexMissing) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RetrievalUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/articles/{document_id}", response_class=HTMLResponse)
def article_page(
    request: Request, document_id: str, q: str = "", profile: str = "bm25",
    backend: RetrievalEngine = Depends(engine),
):
    context = {"back_url": "/?" + urlencode({"q": q, "profile": profile})}
    try:
        item = backend.get_article(document_id)
    except (ArticleNotFound, SearchIndexMissing, RetrievalUnavailable) as exc:
        status = 503 if isinstance(exc, RetrievalUnavailable) else 404
        return templates.TemplateResponse(
            request, "article.html", {**context, "error": str(exc)}, status_code=status
        )
    context.update({
        "article": item,
        "source_url": item.url if urlsplit(item.url).scheme in {"http", "https"} else None,
    })
    return templates.TemplateResponse(request, "article.html", context)
