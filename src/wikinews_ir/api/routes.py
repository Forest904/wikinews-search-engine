"""HTTP endpoints for the initial demo. No dump ingestion in API requests."""

import asyncio
import hashlib
import sqlite3
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlencode, urlsplit

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError

from wikinews_ir.adapters.live import continuation
from wikinews_ir.annotation import database_path
from wikinews_ir.api.schemas import LiveSearchResponse
from wikinews_ir.models import Article, SearchRequest, SearchResponse
from wikinews_ir.operations import check_annotation
from wikinews_ir.reader import read_page
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


def static_asset(filename: str) -> str:
    """Change asset URLs when their contents change, including during local reload."""
    asset = Path(__file__).resolve().parent.parent / "web" / "static" / filename
    version = hashlib.sha256(asset.read_bytes()).hexdigest()[:16]
    return f"/static/{filename}?v={version}"


templates.env.globals["static_asset"] = static_asset


def engine(request: Request) -> RetrievalEngine:
    return request.app.state.engine


@router.get("/", response_class=HTMLResponse)
def home(request: Request):
    return templates.TemplateResponse(request, "index.html", {"profiles": SUPPORTED_PROFILES})


def archive_catalog(backend):
    try:
        return backend.archive()
    except RetrievalUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def ancestors(catalog, path):
    parts = path.split("/")
    return [catalog["/".join(parts[:i])] for i in range(len(parts))] if path else []


@router.get("/archivio/cartelle-home", response_class=HTMLResponse)
def home_folders(request: Request, backend: RetrievalEngine = Depends(engine)):
    root = archive_catalog(backend)[""]
    return templates.TemplateResponse(request, "folder_links.html", {"folder": root})


@router.get("/archivio", response_class=HTMLResponse)
@router.get("/archivio/{path:path}", response_class=HTMLResponse)
def archive_page(request: Request, path: str = "", page: int = Query(1, ge=1),
                 backend: RetrievalEngine = Depends(engine)):
    catalog = archive_catalog(backend)
    folder = catalog.get(path)
    if folder is None or page > max(1, (len(folder.articles) + 29) // 30):
        raise HTTPException(404, "Cartella o pagina non trovata")
    crumbs = ancestors(catalog, path)
    return templates.TemplateResponse(request, "archive.html", dict(
        folder=folder, crumbs=crumbs, back_url=crumbs[-1].url if crumbs else "/",
        profiles=SUPPORTED_PROFILES, page=page, pages=(len(folder.articles) + 29) // 30,
        articles=folder.articles[(page - 1) * 30:page * 30],
    ))


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
    year_from: int | None = Query(None, ge=1, le=9999),
    year_to: int | None = Query(None, ge=1, le=9999),
    limit: str | None = Query(default=None, include_in_schema=False),
):
    try:
        if limit is not None:
            raise HTTPException(status_code=422, detail="Usare page_size al posto di limit")
        search_request = SearchRequest(query=q, profile=profile, page=page, page_size=page_size,
                                       year_from=year_from, year_to=year_to)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail="; ".join(error["msg"] for error in exc.errors())) from exc
    try:
        return backend.search(search_request)
    except SearchIndexMissing as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RetrievalUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.get("/api/search/live", response_model=LiveSearchResponse)
async def live_search(request: Request, q: str = Query(min_length=1, max_length=250),
                      cursor: str = Query("", max_length=512), backend=Depends(engine)):
    q = q.strip()
    if not q:
        raise HTTPException(422, "Inserire una query")
    try:
        continuation(cursor)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    deadline = time.monotonic() + 5
    try:
        page = await request.app.state.wikinews.page(q, cursor, deadline - 0.6)
    except (TimeoutError, httpx.HTTPError, ValueError, KeyError):
        raise HTTPException(503, "Wikinotizie temporaneamente indisponibile") from None
    ids = [hit["document_id"] for hit in page["hits"]]
    remaining = max(0, deadline - time.monotonic())
    try:
        archived = await asyncio.wait_for(asyncio.to_thread(backend.archived_ids, ids, remaining), remaining)
    except TimeoutError:
        archived = set()
    return {**page, "hits": [{**hit, "local_url": "/articles/" + hit["document_id"]
                              if hit["document_id"] in archived else None} for hit in page["hits"]]}


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
    saved_origin = request.query_params.get("view") == "saved"
    back_url = "/"
    back_label = "Home"
    if saved_origin:
        back_url, back_label = "/?view=saved", "Torna ai salvati"
    elif q:
        years = {k: request.query_params[k] for k in ("year_from", "year_to") if request.query_params.get(k)}
        back_url = "/?" + urlencode(dict(q=q, profile=profile, page=page, page_size=page_size, **years))
        if request.query_params.get("mode") == "live":
            back_url = "/?" + urlencode({k: request.query_params[k] for k in
                ("q", "mode", "cursor", "page") if k in request.query_params})
        back_label = "Torna ai risultati"
    context = dict(back_url=back_url, back_label=back_label, query=q,
                   profile=profile, saved_origin=saved_origin)
    try:
        item = backend.get_article(document_id, profile)
    except (ArticleNotFound, SearchIndexMissing, RetrievalUnavailable) as exc:
        status = 503 if isinstance(exc, RetrievalUnavailable) else 404
        return templates.TemplateResponse(
            request, "article.html", {**context, "error": str(exc)}, status_code=status
        )
    origin = request.query_params.get("folder")
    rich = read_page(document_id, item._revision, item._checksum)
    context["rich"] = rich
    try:
        catalog = backend.archive()
    except RetrievalUnavailable:
        catalog = {}
    folder = None
    for candidate in catalog.values() if isinstance(catalog, dict) else ():
        current = next((row for row in candidate.articles if row[2] == document_id), None)
        if current:
            folder = candidate
            break
    if folder:
        excluded = {"/articles/" + document_id}
        excluded.update(link["href"] for link in (rich or {}).get("related", []))
        peers = [row for row in folder.articles if "/articles/" + row[2] not in excluded]
        if current[0]:
            today = date.fromisoformat(current[0])
            peers.sort(key=lambda row: abs((date.fromisoformat(row[0]) - today).days) if row[0] else float("inf"))
        context["peers"] = peers[:3]
        if origin == folder.path and not (q or saved_origin):
            context.update(crumbs=ancestors(catalog, origin) + [folder],
                           back_url=folder.url + "?" + urlencode({"page": page}),
                           back_label="Torna a " + folder.label)
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
