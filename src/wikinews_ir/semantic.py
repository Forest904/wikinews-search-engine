"""Qwen3 embedding document preparation and the Ollama/Qdrant search path."""

import math
import os
import re
import time
from datetime import date

import httpx
from snowballstemmer import stemmer
from tokenizers import Regex, Tokenizer, models, pre_tokenizers

from wikinews_ir.models import SearchHit, SearchResponse
from wikinews_ir.retrieval.profiles import digest

MODEL = "qwen3-embedding:0.6b"
DIM = 1024
QUERY_PREFIX = "Instruct: Retrieve relevant Italian Wikinews articles for this search query.\nQuery: "
ALIAS = "wikinews-semantic"
VERSION = 3
MONTHS = "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split()
STOP = frozenset(
    "a ad al alla alle allo ai agli con da dal dalla dalle dei del della delle degli di e ed è gli i il in la le lo l nel nella nelle negli o per su sul sulla tra un una uno che si".split()
)

# Qwen2 pre-tokenizer from the model's GGUF tokenizer.ggml.pre definition.
PATTERN = r"(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\r\n\p{L}\p{N}]?\p{L}+|\p{N}| ?[^\s\p{L}\p{N}]+[\r\n]*|\s*[\r\n]+|\s+(?!\S)|\s+"


def client(service):
    defaults = {"ollama": "http://127.0.0.1:11434", "qdrant": "http://127.0.0.1:6333"}
    url = os.getenv(service.upper() + "_URL", defaults[service])
    if service == "ollama" and url.startswith("unix:///"):
        return httpx.Client(base_url="http://ollama", transport=httpx.HTTPTransport(uds=url[7:]),
                            timeout=httpx.Timeout(120, connect=5))
    return httpx.Client(
        base_url=url,
        timeout=httpx.Timeout(120, connect=5),
    )


def call(http, method, path, **kwargs):
    result = http.request(method, path, **kwargs)
    result.raise_for_status()
    return result.json()


def identity(http):
    for entry in call(http, "GET", "/api/tags")["models"]:
        if entry["name"] == MODEL:
            return {
                "model": MODEL,
                "digest": entry["digest"],
                "runtime": call(http, "GET", "/api/version")["version"],
                "version": VERSION,
                "dimensions": DIM,
                "metric": "Cosine",
                "tokens": 256,
                "document": "title: {title}\ncontent: {body}",
                "query": QUERY_PREFIX + "{query}",
                "tokenizer": "qwen2-gguf",
                "num_ctx": 2048,
            }
    raise ValueError(f"Modello Ollama mancante: {MODEL}")


def tokenizer(http):
    info = call(http, "POST", "/api/show", json={"model": MODEL, "verbose": True})["model_info"]
    if info["tokenizer.ggml.pre"] != "qwen2" or info["tokenizer.ggml.add_bos_token"]:
        raise ValueError("Tokenizer Ollama incompatibile")
    vocab = dict(
        zip(info["tokenizer.ggml.tokens"], range(len(info["tokenizer.ggml.tokens"])), strict=True)
    )
    merges = [tuple(pair.split(" ")) for pair in info["tokenizer.ggml.merges"]]
    tok = Tokenizer(models.BPE(vocab, merges))
    tok.pre_tokenizer = pre_tokenizers.Sequence(
        [
            pre_tokenizers.Split(Regex(PATTERN), behavior="isolated"),
            pre_tokenizers.ByteLevel(add_prefix_space=False, use_regex=False),
        ]
    )
    from tokenizers.processors import TemplateProcessing

    if info.get("tokenizer.ggml.add_eos_token"):
        eid = info["tokenizer.ggml.eos_token_id"]
        eos = info["tokenizer.ggml.tokens"][eid]
        tok.post_processor = TemplateProcessing(single=f"$A {eos}", special_tokens=[(eos, eid)])
    return tok


def transform(text, variant):
    if variant == "natural":
        return text
    words = [w for w in re.findall(r"\w+", text.casefold()) if w not in STOP]
    return " ".join(stemmer("italian").stemWords(words))


def opening(body, published):
    lines = [
        re.sub(r"[ \t]+", " ", re.sub(r"https?://[^\s<>]+", "", line)).strip()
        for line in body.splitlines()
    ]
    lines = [line for line in lines if line]
    if published and lines:
        day = date.fromisoformat(published)
        stamp = f"{day.day} {MONTHS[day.month - 1]} {day.year}"
        weekday = r"(?:(?:lunedì|martedì|mercoledì|giovedì|venerdì|sabato|domenica) )?"
        match = re.fullmatch(r"(?:(.{1,80}), )?" + weekday + stamp, lines[0], re.I)
        if match:
            lines[:1] = [match[1]] if match[1] else []
    return "\n".join(lines)


def token_prefix(text, tok, budget):
    encoded = tok.encode(text)
    while len(encoded.ids) > budget:
        # One Unicode character can cover several byte-level tokens.
        end = min(encoded.offsets[budget - 1][1], len(text) - 1)
        text = text[:end]
        encoded = tok.encode(text)
    return text, len(encoded.ids)


def prepare(article, body, tok, variant):
    published = (
        article["publication_date"] if article["publication_date_status"] == "validated" else None
    )
    lead = opening(body, published)
    title = article["title"].strip()
    if not (title or lead):
        return None
    heading = transform(title, variant)
    if len(tok.encode(f"title: {heading}\ncontent: ").ids) > 256:
        budget = 256 - len(tok.encode("title: \ncontent: ").ids)
        heading, _ = token_prefix(heading, tok, budget)
    text, tokens = token_prefix(f"title: {heading}\ncontent: {transform(lead, variant)}", tok, 256)
    return {
        "input": text,
        "tokens": tokens,
        "document_id": str(article["document_id"]),
        "revision_id": str(article["revision_id"]),
        "title": title,
        "snippet": lead[:240],
        "url": article["url"],
        "publication_date": published,
        "year": int(published[:4]) if published else None,
    }


def measured_embeddings(http, texts):
    result = call(
        http,
        "POST",
        "/api/embed",
        timeout=600 if len(texts) > 1 else 120,
        json={"model": MODEL, "input": texts, "truncate": False, "options": {"num_ctx": 2048}},
    )
    vectors = result["embeddings"]
    if len(vectors) != len(texts):
        raise ValueError("Batch Ollama incompleto")
    normalized = []
    for vector in vectors:
        norm = math.hypot(*vector)
        if len(vector) != DIM or not math.isfinite(norm) or norm == 0:
            raise ValueError("Embedding Ollama non valido")
        normalized.append([v / norm for v in vector])
    return normalized, result["prompt_eval_count"]


def embed(http, texts, expected_tokens=None):
    vectors, count = measured_embeddings(http, texts)
    if expected_tokens is not None and count != expected_tokens:
        raise ValueError("Conteggio token locale diverso da Ollama")
    return vectors


def embed_documents(model, rows, tok):
    vectors, count = measured_embeddings(model, [row["input"] for row in rows])
    if count == sum(row["tokens"] for row in rows):
        return vectors
    verified = []
    for row in rows:
        text = row["input"]
        while True:
            (vector,), actual = measured_embeddings(model, [text])
            if actual <= 256:
                break
            budget = max(1, len(tok.encode(text).ids) - (actual - 256))
            shorter, _ = token_prefix(text, tok, budget)
            text = shorter if len(shorter) < len(text) else text[:-1]
            if not text:
                raise ValueError(f"Input non riducibile: {row['document_id']}")
        row.update(input=text, tokens=actual)
        verified.append(vector)
    return verified


def collection_for(db, alias):
    aliases = call(db, "GET", "/aliases")["result"]["aliases"]
    for row in aliases:
        if row["alias_name"] == alias:
            return row["collection_name"]
    raise ValueError("Indice semantico non attivo")


def search(request, *, variant="natural", exact=None, timings=None):
    started = time.monotonic()
    if exact is None:
        exact = os.getenv("SEMANTIC_EXACT", "1") == "1"
    alias = ALIAS if variant == "natural" else ALIAS + "-stem"
    with client("ollama") as model, client("qdrant") as db:
        name = collection_for(db, alias)
        encoder = identity(model)
        prefix = f"news-{digest(encoder)[:24]}-{variant}-"
        if not name.startswith(prefix):
            raise ValueError("Modello e indice semantico incompatibili")
        embed_start = time.perf_counter()
        (vector,) = embed(model, [QUERY_PREFIX + transform(request.query, variant)])
        vector_start = time.perf_counter()
        if timings is not None:
            timings["embedding_ms"] = (vector_start - embed_start) * 1000
        bounds = {k: v for k, v in (("gte", request.year_from), ("lte", request.year_to)) if v}
        filters = {"filter": {"must": [{"key": "year", "range": bounds}]}} if bounds else {}
        base = "/collections/" + name + "/points"
        total = call(db, "POST", base + "/count", json={"exact": True, **filters})["result"][
            "count"
        ]
        start = (request.page - 1) * request.page_size
        end = start + request.page_size
        limit = min(total, end + 1)
        points = []
        while start < total:
            points = call(
                db,
                "POST",
                base + "/query",
                json={
                    "query": vector,
                    **filters,
                    "params": {"exact": exact},
                    "limit": limit,
                    "with_payload": True,
                },
            )["result"]["points"]
            points.sort(key=lambda p: (-p["score"], p["payload"]["document_id"]))
            if (
                limit >= total
                or len(points) <= end
                or points[end - 1]["score"] != points[-1]["score"]
            ):
                break
            limit = min(total, limit * 2)
        if timings is not None:
            timings["count_and_query_ms"] = (time.perf_counter() - vector_start) * 1000
    hits = [
        SearchHit(**p["payload"], score=p["score"], rank=i)
        for i, p in enumerate(points[start:end], start + 1)
    ]
    return SearchResponse(
        query=request.query,
        profile="semantic",
        index=name,
        hits=hits,
        total=total,
        page=request.page,
        page_size=request.page_size,
        metadata={"encoder": encoder, "variant": variant, "exact": exact},
        elapsed_ms=int((time.monotonic() - started) * 1000),
    )
