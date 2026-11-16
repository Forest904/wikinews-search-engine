"""Authenticated annotation and coordination endpoints; no retrieval dependencies."""

import hashlib
import io
import os
import secrets
import sqlite3
import tempfile
import time
import zipfile
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, ConfigDict, Field, StrictInt

from wikinews_ir.annotation import (
    audit,
    authenticate,
    connect,
    database_path,
    now,
    own_history,
    require_coordinator,
    save,
    tasks,
    transaction,
)
from wikinews_ir.annotation_export import export_snapshot, write_export
from wikinews_ir.annotation_workflow import (
    activate_block,
    adjudicate,
    assign_review,
    block_preview,
    create_block,
    dashboard,
    review_tasks,
)

router = APIRouter(prefix="/api/annotation")


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Login(Input):
    user_id: str = Field(min_length=1, max_length=80)
    password: str = Field(min_length=1, max_length=1024)


class Pair(Input):
    packet_id: str = Field(min_length=1, max_length=128)
    query_id: str = Field(min_length=1, max_length=250)
    document_id: str = Field(min_length=1, max_length=250)

    def key(self):
        return self.packet_id, self.query_id, self.document_id


class Submission(Pair):
    expected_version: StrictInt = Field(ge=0)
    request_id: str = Field(min_length=1, max_length=128)
    status: Literal["judged", "needs_review", "deferred"]
    grade: StrictInt | None = Field(default=None, ge=0, le=2)
    rationale: str = Field(default="", max_length=10000)
    evidence: list[dict] = Field(default_factory=list, max_length=100)


class Block(Input):
    packet_id: str
    query_id: str
    primary_user: str
    secondary_user: str | None = None
    third_user: str | None = None
    overlap: StrictInt = Field(ge=0)
    seed: str = Field(min_length=1, max_length=100)


class ReviewAssignment(Pair):
    reviewer: str


class Decision(Pair):
    basis: str
    request_id: str = Field(min_length=1, max_length=128)
    status: Literal["judged", "needs_review"]
    grade: StrictInt | None = Field(default=None, ge=0, le=2)
    rationale: str = Field(min_length=1, max_length=10000)
    evidence: list[dict] = Field(default_factory=list, max_length=100)


class Export(Input):
    packet_id: str
    split: Literal["calibration", "development", "test"] = "development"
    release_test: bool = False


class Timer(Pair):
    timer_id: str = Field(min_length=1, max_length=128)
    phase: Literal["reading", "annotation", "review"]
    seconds: float = Field(default=0, ge=0, le=86400, allow_inf_nan=False)
    stop: bool = False


class Discussion(Input):
    packet_id: str
    minutes: float | None = Field(default=None, gt=0, le=1440, allow_inf_nan=False)
    participants: list[str] | None = None
    notes: str | None = Field(default=None, max_length=30000)


@router.post("/timing")
def timing_checkpoint(body: Timer, request: Request):
    from wikinews_ir.pilot import timer
    with access(request, True) as (db, user):
        return timer(db, user["user_id"], body.timer_id, body.key(), body.phase,
                     body.seconds, body.stop)


@router.post("/pilot-discussion")
def pilot_discussion(body: Discussion, request: Request):
    from wikinews_ir.pilot import discussion
    with access(request, True) as (db, user):
        return discussion(db, user["user_id"], **body.model_dump())


def check_origin(request):
    origin = request.headers.get("origin")
    if origin and origin != str(request.base_url).rstrip("/"):
        raise HTTPException(403, "Origine non valida")
    if request.headers.get("sec-fetch-site") == "cross-site":
        raise HTTPException(403, "Richiesta da un altro sito non ammessa")


def identity(request, db, mutate=False):
    token = request.cookies.get("annotation_session", "")
    key = hashlib.sha256(token.encode()).hexdigest()
    row = db.execute("SELECT s.user_id,u.coordinator,c.csrf FROM sessions s JOIN users u "
                     "ON u.id=s.user_id JOIN session_csrf c ON c.token_hash=s.token_hash "
                     "WHERE s.token_hash=? AND s.expires>?", (key, now())).fetchone()
    if not token or row is None:
        raise HTTPException(401, "Accesso richiesto")
    if mutate:
        check_origin(request)
        if not secrets.compare_digest(request.headers.get("x-csrf-token", ""), row["csrf"]):
            raise HTTPException(403, "Sessione non valida: ricarica la pagina")
    return dict(row)


@contextmanager
def access(request, mutate=False):
    try:
        with connect(database_path()) as db:
            yield db, identity(request, db, mutate)
    except PermissionError as exc:
        raise HTTPException(403, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(409, str(exc)) from exc
    except (ValueError, sqlite3.IntegrityError) as exc:
        raise HTTPException(422, str(exc)) from exc
    except sqlite3.OperationalError as exc:
        raise HTTPException(503, "Archivio temporaneamente non disponibile; riprova") from exc


@router.post("/login")
def login(body: Login, request: Request):
    check_origin(request)
    timestamp = time.time()
    # Both account and address limits survive process restarts. No proxy header is trusted here.
    keys = [f"user:{body.user_id}", f"ip:{request.client.host if request.client else 'local'}"]
    with connect(database_path()) as db:
        with transaction(db):
            for key, limit in zip(keys, (10, 50), strict=True):
                row = db.execute("SELECT * FROM login_attempts WHERE key=?", (key,)).fetchone()
                if row and row["reset_at"] > timestamp and row["attempts"] >= limit:
                    raise HTTPException(429, "Troppi tentativi: riprova fra 15 minuti")
                db.execute("INSERT INTO login_attempts VALUES(?,1,?) ON CONFLICT(key) DO UPDATE "
                           "SET attempts=CASE WHEN reset_at<=? THEN 1 ELSE attempts+1 END, "
                           "reset_at=CASE WHEN reset_at<=? THEN ? ELSE reset_at END",
                           (key, timestamp + 900, timestamp, timestamp, timestamp + 900))
        if not authenticate(db, body.user_id, body.password):
            raise HTTPException(401, "Credenziali non valide")
        token, csrf = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        digest = hashlib.sha256(token.encode()).hexdigest()
        with transaction(db):
            old = request.cookies.get("annotation_session", "")
            db.execute("DELETE FROM sessions WHERE token_hash=? OR expires<=?",
                       (hashlib.sha256(old.encode()).hexdigest(), now()))
            db.execute("INSERT INTO sessions VALUES(?,?,?)", (digest, body.user_id,
                       (datetime.now(UTC) + timedelta(hours=12)).isoformat()))
            db.execute("INSERT INTO session_csrf VALUES(?,?)", (digest, csrf))
            db.execute("DELETE FROM login_attempts WHERE key=?", (keys[0],))
            audit(db, body.user_id, "login")
        coordinator = bool(db.execute("SELECT coordinator FROM users WHERE id=?",
                                      (body.user_id,)).fetchone()[0])
    response = JSONResponse({"user_id": body.user_id, "coordinator": coordinator, "csrf": csrf})
    response.set_cookie("annotation_session", token, httponly=True, samesite="strict",
                        secure=os.getenv("ANNOTATION_COOKIE_SECURE", "0") == "1"
                        or request.url.scheme == "https", max_age=43200)
    response.headers["Cache-Control"] = "no-store"
    return response


@router.get("/session")
def session(request: Request):
    with access(request) as (_, user):
        return user


@router.post("/logout")
def logout(request: Request):
    with access(request, True) as (db, user):
        digest = hashlib.sha256(request.cookies["annotation_session"].encode()).hexdigest()
        db.execute("DELETE FROM sessions WHERE token_hash=?", (digest,))
        audit(db, user["user_id"], "logout")
    response = JSONResponse({"logged_out": True})
    response.delete_cookie("annotation_session")
    return response


@router.get("/tasks")
def list_tasks(request: Request):
    with access(request) as (db, user):
        return tasks(db, user["user_id"])


@router.get("/history")
def history(request: Request, packet_id: str, query_id: str, document_id: str):
    with access(request) as (db, user):
        return own_history(db, user["user_id"], (packet_id, query_id, document_id))


@router.post("/judgments")
def submit(body: Submission, request: Request):
    with access(request, True) as (db, user):
        version = save(db, user["user_id"], **body.model_dump())
        return {"version": version, "saved": True}


@router.get("/dashboard")
def coordinate(request: Request):
    with access(request) as (db, user):
        return dashboard(db, user["user_id"])


@router.post("/blocks")
def prepare_block(body: Block, request: Request):
    with access(request, True) as (db, user):
        return create_block(db, user["user_id"], **body.model_dump())


@router.post("/blocks/{block_id}/activate")
def activate(block_id: str, request: Request):
    with access(request, True) as (db, user):
        return activate_block(db, user["user_id"], block_id)


@router.get("/blocks/{block_id}")
def read_block(block_id: str, request: Request):
    with access(request) as (db, user):
        require_coordinator(db, user["user_id"])
        row = db.execute("SELECT * FROM blocks WHERE id=?", (block_id,)).fetchone()
        if not row:
            raise HTTPException(404, "Blocco inesistente")
        return block_preview(db, dict(row))


@router.post("/review-assignments")
def assign_reviewer(body: ReviewAssignment, request: Request):
    with access(request, True) as (db, user):
        assign_review(db, user["user_id"], body.key(), body.reviewer)
        return {"saved": True}


@router.get("/reviews")
def reviews(request: Request):
    with access(request) as (db, user):
        return review_tasks(db, user["user_id"])


@router.post("/decisions")
def decision(body: Decision, request: Request):
    with access(request, True) as (db, user):
        decision_id = adjudicate(db, user["user_id"], body.key(), body.basis, body.request_id,
                                 body.status, body.grade, body.rationale, body.evidence)
        return {"saved": True, "decision_id": decision_id}


@router.post("/exports")
def export(body: Export, request: Request):
    with access(request, True) as (db, user):
        snapshot = export_snapshot(db, user["user_id"], **body.model_dump())
    with tempfile.TemporaryDirectory() as temporary:
        output = Path(temporary) / "export"
        write_export(snapshot, output)
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(output.iterdir()):
                archive.write(path, path.name)
    return Response(buffer.getvalue(), media_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="gold-{body.split}.zip"',
        "Cache-Control": "no-store"})
