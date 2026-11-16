"""HTTP endpoints for the initial demo. No dump ingestion in API requests."""

import sqlite3
from pathlib import Path
from urllib.parse import urlencode, urlsplit

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from wikinews_ir.annotation import database_path
from wikinews_ir.models import Article, SearchRequest, SearchResponse
from wikinews_ir.operations import check_annotation
from wikinews_ir.retrieval.engine import (
    ArticleNotFound,
    RetrievalEngine,
    RetrievalUnavailable,
    SearchIndexMissing,
)
from wikinews_ir.retrieval.profiles import SUPPORTED_PROFILES, ProfileId

router = APIRouter()
templates = Jinja2Templates(
    directory=str(Path(__file__).resolve().parent.parent / "web" / "templates")
)


def engine(request: Request) -> RetrievalEngine:
    return request.app.state.engine


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "index.html", {"profiles": SUPPORTED_PROFILES})


@router.get("/annotate", response_class=HTMLResponse)
def annotate(request: Request):
    return templates.TemplateResponse(request, "annotate.html")


@router.get("/coordinate", response_class=HTMLResponse)
def coordinate(request: Request):
    return templates.TemplateResponse(request, "coordinate.html")


@router.get("/api/health/live")
def live():
    return {"app": "ok"}


@router.get("/api/health/annotation")
def annotation_health():
    try:
        check_annotation(database_path())
    except (sqlite3.Error, OSError, ValueError):
        raise HTTPException(status_code=503, detail={"annotation": "unavailable"}) from None
    return {"annotation": "ready"}


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
    profile: ProfileId = "E0",
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    limit: str | None = Query(default=None, include_in_schema=False),
):
    try:
        if limit is not None:
            raise HTTPException(status_code=422, detail="Usare page_size al posto di limit")
        search_request = SearchRequest(query=q, profile=profile, page=page, page_size=page_size)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="; ".join(error["msg"] for error in exc.errors())) from exc
    try:
        return backend.search(search_request)
    except SearchIndexMissing as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RetrievalUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/api/articles/{document_id}", response_model=Article)
def article(document_id: str, profile: ProfileId = "E0",
            backend: RetrievalEngine = Depends(engine)):
    try:
        return backend.get_article(document_id, profile)
    except (ArticleNotFound, SearchIndexMissing) as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RetrievalUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/articles/{document_id}", response_class=HTMLResponse)
def article_page(
    request: Request, document_id: str, q: str = "",
    profile: ProfileId = "E0",
    page: int = Query(default=1, ge=1), page_size: int = Query(default=10, ge=1, le=100),
    backend: RetrievalEngine = Depends(engine),
):
    context = {"back_url": "/?" + urlencode({"q": q, "profile": profile, "page": page, "page_size": page_size})}
    try:
        item = backend.get_article(document_id, profile)
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


@router.get("/api/ready")
def ready(backend: RetrievalEngine = Depends(engine)):
    try:
        return {"ready": True, "profiles": backend.readiness()}
    except RetrievalUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
