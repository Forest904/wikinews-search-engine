"""MediaWiki Action API search capture/replay; never a relevance judge."""

import json
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import quote

import httpx

from wikinews_ir.adapters.mediawiki import ENDPOINT, MediaWiki
from wikinews_ir.evaluation.artifacts import encoded, file_sha, jsonl, write_bundle
from wikinews_ir.evaluation.benchmark import corpus_data, load_topics


def capture(topics, top_k, user_agent, client=None, sleep=time.sleep, audit=None):
    api = MediaWiki(user_agent, client, sleep)
    pages = []
    audit = audit if audit is not None else []
    try:
        for topic in topics:
            continuation, seen = {}, set()
            count = 0
            while count < top_k:
                params = {"action": "query", "list": "search", "format": "json",
                          "formatversion": 2, "srnamespace": 0, "srsearch": topic["query"],
                          "srlimit": min(50, top_k - count), "maxlag": 5, **continuation}
                data = api.query(params, audit=lambda entry: audit.append(
                    {"query_id": topic["query_id"], **entry}))
                hits = data["query"]["search"]
                pages.append({"query_id": topic["query_id"], "params": params,
                              "captured_at": datetime.now(UTC).isoformat(), "response": data})
                count += len(hits)
                if not data.get("continue"):
                    break
                token = json.dumps(data["continue"], sort_keys=True)
                if not hits or token in seen:
                    raise ValueError("Paginazione MediaWiki bloccata")
                seen.add(token)
                continuation = data["continue"]
        return {"endpoint": ENDPOINT, "top_k": top_k, "pages": pages, "attempts": audit}
    finally:
        api.close()


def normalize(archive, topics, docs, top_k):
    if archive["endpoint"] != ENDPOINT or archive["top_k"] != top_k:
        raise ValueError("Endpoint o profondità archivio incompatibile")
    wanted = {t["query_id"]: t["query"] for t in topics}
    if any(p["query_id"] not in wanted for p in archive["pages"]):
        raise ValueError("Query inattesa nell'archivio")
    results = []
    for qid, query in wanted.items():
        pages = [p for p in archive["pages"] if p["query_id"] == qid]
        if not pages:
            raise ValueError("Archivio incompleto: query mancante")
        count, continuation, seen, tokens = 0, {}, set(), set()
        for i, page in enumerate(pages):
            params, response = page["params"], page["response"]
            expected = {"action": "query", "list": "search", "format": "json",
                        "formatversion": 2, "srnamespace": 0, "srsearch": query,
                        "srlimit": min(50, top_k-count), "maxlag": 5, **continuation}
            if params != expected or "error" in response or "warnings" in response:
                raise ValueError("Parametri o risposta archivio non validi")
            if datetime.fromisoformat(page["captured_at"]).tzinfo is None:
                raise ValueError("Timestamp senza fuso")
            hits = response["query"]["search"]
            if not isinstance(hits, list) or len(hits) > params["srlimit"]:
                raise ValueError("Numero risultati non valido")
            for hit in hits:
                if type(hit["pageid"]) is not int or hit["pageid"] <= 0 or hit["ns"] != 0:
                    raise ValueError("Page ID/namespace non valido")
                did = str(hit["pageid"])
                if did in seen:
                    raise ValueError("Risultato Wikimedia duplicato")
                seen.add(did)
                count += 1
                results.append({"query_id": qid, "document_id": did, "rank": count,
                                "title": hit["title"], "in_corpus": did in docs,
                                "url": "https://it.wikinews.org/wiki/" + quote(
                                    hit["title"].replace(" ", "_"), safe=""),
                                "captured_at": page["captured_at"]})
            continuation = response.get("continue", {})
            token = json.dumps(continuation, sort_keys=True)
            if continuation and (not hits or token in tokens):
                raise ValueError("Continuation non valida")
            tokens.add(token)
            complete = count >= top_k or not continuation
            if complete and i != len(pages)-1:
                raise ValueError("Pagine superflue nell'archivio")
        if count < top_k and continuation:
            raise ValueError("Archivio parziale: continuation non acquisita")
    return results


def external_run(topics_path, corpus, output, top_k=100, replay=None, user_agent=None,
                 client=None, sleep=time.sleep):
    if type(top_k) is not int or not 1 <= top_k <= 1000:
        raise ValueError("top-k deve essere tra 1 e 1000")
    topics = load_topics(topics_path)
    identity, docs = corpus_data(corpus)
    if Path(output).exists():
        raise ValueError("La directory di output esiste già")
    audit = []
    try:
        archive = json.loads(Path(replay).read_text("utf-8")) if replay else capture(
            topics, top_k, user_agent, client, sleep, audit
        )
    except (httpx.HTTPError, ValueError, KeyError, TypeError) as exc:
        if audit:
            write_bundle(output, "external-run-failed", {
                "failure.json": encoded({"error": str(exc), "attempts": audit})
            }, {"complete": False, "corpus": identity})
        raise
    results = normalize(archive, topics, docs, top_k)
    trec = []
    for topic in topics:
        mapped = [r for r in results if r["query_id"] == topic["query_id"] and r["in_corpus"]]
        for rank, row in enumerate(mapped, 1):
            trec.append(f"{row['query_id']} Q0 {row['document_id']} {rank} "
                        f"{1/rank:.12g} wikimedia\n")
    return write_bundle(output, "external-run", {
        "archive.json": encoded(archive), "results.jsonl": jsonl(results),
        "wikimedia.trec": "".join(trec),
    }, {"corpus": identity, "queries": {t["query_id"]: t["query"] for t in topics},
        "top_k": top_k, "mode": "replay" if replay else "live", "complete": True,
        "archive_input_sha256": file_sha(replay) if replay else None,
        "unmapped": sum(not r["in_corpus"] for r in results),
        "trec_policy": "in-corpus projection, consecutive ranks, conventional score 1/rank"})
