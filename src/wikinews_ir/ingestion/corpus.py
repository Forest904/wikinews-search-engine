"""Versioned, offline Enterprise HTML corpus pipeline."""

import hashlib
import importlib.metadata
import json
import math
import re
import sqlite3
import subprocess
import tarfile
import tempfile
import unicodedata
from collections import Counter
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from bs4 import BeautifulSoup
from pydantic import BaseModel, Field

PIPELINE_VERSION = "1.0.0"
SNAPSHOT = "itwikinews-20250320"
MONTHS = dict(
    zip(
        "gennaio febbraio marzo aprile maggio giugno luglio agosto settembre ottobre novembre dicembre".split(),
        range(1, 13),
        strict=True,
    )
)


class ProcessedArticle(BaseModel):
    document_id: str
    revision_id: str
    title: str = Field(min_length=1)
    body: str = Field(min_length=1)
    url: str
    categories: list[str]
    publication_date: date | None
    publication_date_status: Literal["validated", "missing", "invalid", "ambiguous"]
    publication_date_evidence: list[str]
    sources: list[dict]
    license: list[dict]
    provenance: dict


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def checksum(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def records(path):
    """Yield physical locations and decoded records, including localized errors."""

    def lines(stream, member):
        for number, raw in enumerate(stream, 1):
            try:
                record = json.loads(raw.decode("utf-8"))
                yield member, number, record, None
            except (UnicodeError, ValueError) as exc:
                yield member, number, None, str(exc)

    path = Path(path)
    if path.name.endswith(".tar.gz"):
        found = False
        with tarfile.open(path, "r|gz") as archive:
            for member in archive:
                if member.isfile() and member.name.endswith((".ndjson", ".jsonl")):
                    found = True
                    with archive.extractfile(member) as stream:
                        yield from lines(stream, member.name)
        if not found:
            raise tarfile.ReadError("Archive contains no regular NDJSON members")
    else:
        with path.open("rb") as stream:
            yield from lines(stream, path.name)


def validate_raw(record):
    if not isinstance(record, dict):
        raise ValueError("Record must be an object")
    for value in (record.get("identifier"), record.get("version", {}).get("identifier")):
        if type(value) is not int or not 1 <= value <= 2**63 - 1:
            raise ValueError("Page and revision identifiers must be positive 64-bit integers")
    for key in ("name", "url"):
        if not isinstance(record.get(key), str) or not record[key].strip():
            raise ValueError(f"Invalid {key}")
    for key in ("namespace", "in_language", "article_body"):
        if not isinstance(record.get(key), dict):
            raise ValueError(f"Invalid {key}")
    if type(record["namespace"].get("identifier")) is not int:
        raise ValueError("Invalid namespace identifier")
    if not isinstance(record["in_language"].get("identifier"), str):
        raise ValueError("Invalid language identifier")
    if not isinstance(record["article_body"].get("html"), str):
        raise ValueError("Missing HTML")
    for key in ("categories", "license"):
        values = record.get(key, [])
        if not isinstance(values, list) or any(not isinstance(v, dict) for v in values):
            raise ValueError(f"Invalid {key}")
    if any(not isinstance(c.get("name"), str) for c in record.get("categories", [])):
        raise ValueError("Invalid category name")


def normalized(text):
    return re.sub(r"\s+", " ", unicodedata.normalize("NFC", text)).strip()


def publication_date(soup):
    evidence = []
    values = []
    invalid = False
    for node in soup.select("[data-mw]"):
        try:
            parts = json.loads(node["data-mw"]).get("parts", [])
        except (ValueError, AttributeError):
            continue
        for part in parts:
            if not isinstance(part, dict) or "template" not in part:
                continue
            template = part["template"]
            name = template.get("target", {}).get("href", "").lower()
            if name not in ("./template:data", "./template:luogodata"):
                continue
            params = template.get("params", {})
            key = "1" if name.endswith(":data") else "data"
            raw = normalized(params.get(key, {}).get("wt", ""))
            evidence.append(f"{name}:{raw}")
            match = re.fullmatch(r"(\d{1,2})\s+([a-z]+)\s+(\d{4})", raw.lower())
            try:
                if not match:
                    raise ValueError("Unrecognized date")
                day, month, year = match.groups()
                values.append(date(int(year), MONTHS[month], int(day)))
            except (ValueError, KeyError):
                invalid = True
    if not evidence:
        return None, "missing", []
    if len(set(values)) > 1:
        return None, "ambiguous", evidence
    if invalid or not values:
        return None, "invalid", evidence
    return values[0], "validated", evidence


def clean_html(html):
    soup = BeautifulSoup(html, "lxml")
    pubdate, status, evidence = publication_date(soup)
    sources = []
    for node in list(soup.select("table[data-mw],div[data-mw]")):
        if node.parent is None:
            continue
        try:
            parts = json.loads(node["data-mw"]).get("parts", [])
        except (ValueError, AttributeError):
            continue
        names = [
            part["template"].get("target", {}).get("href", "").casefold()
            for part in parts
            if isinstance(part, dict) and "template" in part
        ]
        if names and all(name == "./template:notizia_originale" for name in names):
            node.decompose()
    for node in list(soup.select("p")):
        text = normalized(node.get_text(" ", strip=True))
        if text.startswith("Per vedere il calendario completo vai alla pagina Speciale"):
            node.decompose()
    for node in list(soup.select("sup.reference")):
        node.decompose()
    for node in list(
        soup.select(
            "head,script,style,nav,footer,.metadata,.noprint,.boilerplate,.navbox,.toc,.mw-editsection,#commentrequest,#condivisione-articolo,link,meta"
        )
    ):
        if node.parent is not None:
            node.decompose()
    # Remove only the section governed by each heading, not later article sections.
    for heading in list(soup.select("h2,h3,h4")):
        label = normalized(heading.get_text(" ", strip=True)).casefold()
        if label not in {
            "fonti",
            "note",
            "articoli correlati",
            "vedi anche",
            "collegamenti esterni",
            "altri progetti",
        }:
            continue
        level = int(heading.name[1])
        nodes = []
        for sibling in heading.next_siblings:
            if getattr(sibling, "name", None) in {f"h{i}" for i in range(1, level + 1)}:
                break
            nodes.append(sibling)
        if label in {"fonti", "note"}:
            for node in nodes:
                if not hasattr(node, "select"):
                    continue
                citations = node.select("cite")
                if getattr(node, "name", None) == "cite":
                    citations = [node]
                for cite in citations:
                    sources.append(
                        {
                            "text": normalized(cite.get_text(" ", strip=True)),
                            "urls": [
                                a["href"]
                                for a in cite.select("a[href]")
                                if a["href"].startswith(("http://", "https://"))
                            ],
                        }
                    )
                if not citations and normalized(node.get_text(" ", strip=True)):
                    sources.append(
                        {
                            "text": normalized(node.get_text(" ", strip=True)),
                            "urls": [
                                a["href"]
                                for a in node.select("a[href]")
                                if a["href"].startswith(("http://", "https://"))
                            ],
                        }
                    )
        for node in nodes:
            node.extract()
        heading.decompose()
    for node in list(
        soup.select(
            "head,script,style,nav,footer,.metadata,.noprint,.boilerplate,.navbox,.toc,.mw-editsection,#commentrequest,#condivisione-articolo,link,meta"
        )
    ):
        if node.parent is not None:
            node.decompose()
    for node in list(soup.select("[style]")):
        if re.search(r"display\s*:\s*none", node.get("style", ""), re.I):
            node.decompose()
    root = soup.body or soup
    for br in root.select("br"):
        br.replace_with("\n")
    for cell in root.select("td,th"):
        cell.append(" | ")
    for block in root.select("p,div,section,h1,h2,h3,h4,li,tr,blockquote,figcaption"):
        block.insert_before("\n")
        block.insert_after("\n")
    text = root.get_text()
    body = "\n".join(line for raw in text.splitlines() if (line := normalized(raw)))
    return body, sources, pubdate, status, evidence


def exclusion(record):
    if record["namespace"]["identifier"] != 0:
        return "namespace"
    if record["in_language"]["identifier"] != "it":
        return "language"
    if "Categoria:Pubblicati" not in [c["name"] for c in record.get("categories", [])]:
        return "not_published"
    parsed = urlparse(record["url"])
    if (
        parsed.scheme != "https"
        or parsed.netloc != "it.wikinews.org"
        or not parsed.path.startswith("/wiki/")
    ):
        return "invalid_url"
    html = record["article_body"]["html"]
    if re.search(r"rel=[\"\']mw:PageProp/redirect[\"\']", html, re.I) or re.match(
        r"\s*#(?:redirect|rinvia)\b", record["article_body"].get("wikitext", ""), re.I
    ):
        return "redirect"
    if any(c["name"] == "Categoria:Da cancellare subito" for c in record.get("categories", [])):
        return "non_article"
    return None


def git_info():
    def run(*args):
        try:
            return subprocess.check_output(
                ["git", *args],
                cwd=Path(__file__).resolve().parents[3],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        except (OSError, subprocess.CalledProcessError):
            return None

    status = run("status", "--porcelain")
    return {"commit": run("rev-parse", "HEAD"), "dirty": None if status is None else bool(status)}


def run_corpus(input_path, output_path, *, audit_only=False):
    input_path, output_path = Path(input_path).resolve(), Path(output_path).resolve()
    if output_path.exists() and (not output_path.is_dir() or any(output_path.iterdir())):
        raise ValueError("Output directory must be absent or empty")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    source_hash = checksum(input_path)
    with tempfile.TemporaryDirectory(prefix=".corpus-", dir=output_path.parent) as temporary:
        stage = Path(temporary)
        db = sqlite3.connect(stage / "records.sqlite")
        try:
            db.execute(
                "CREATE TABLE revisions (id INTEGER, revision INTEGER, payload TEXT, member TEXT, line INTEGER, PRIMARY KEY(id,revision))"
            )
            counts = Counter(
                dict.fromkeys(
                    (
                        "records_read",
                        "invalid_records",
                        "published_records",
                        "identical_duplicate",
                        "revision_conflict",
                        "archive_errors",
                        "superseded_revisions",
                    ),
                    0,
                )
            )
            published_ids = set()
            with (stage / "decisions.ndjson").open(
                "w", encoding="utf-8", newline="\n"
            ) as decisions:

                def log(**value):
                    decisions.write(canonical(value) + "\n")

                try:
                    for member, line, record, error in records(input_path):
                        counts["records_read"] += 1
                        try:
                            if error:
                                raise ValueError(error)
                            validate_raw(record)
                        except (ValueError, TypeError, AttributeError) as exc:
                            counts["invalid_records"] += 1
                            log(reason="invalid_record", member=member, line=line, error=str(exc))
                            continue
                        ident, revision = record["identifier"], record["version"]["identifier"]
                        if "Categoria:Pubblicati" in [
                            c["name"] for c in record.get("categories", [])
                        ]:
                            counts["published_records"] += 1
                            published_ids.add(ident)
                        payload = canonical(record)
                        previous = db.execute(
                            "SELECT payload FROM revisions WHERE id=? AND revision=?",
                            (ident, revision),
                        ).fetchone()
                        if previous:
                            reason = (
                                "identical_duplicate"
                                if previous[0] == payload
                                else "revision_conflict"
                            )
                            counts[reason] += 1
                            log(
                                reason=reason,
                                document_id=str(ident),
                                revision_id=str(revision),
                                member=member,
                                line=line,
                            )
                            continue
                        db.execute(
                            "INSERT INTO revisions VALUES (?,?,?,?,?)",
                            (ident, revision, payload, member, line),
                        )
                except (tarfile.TarError, EOFError, OSError) as exc:
                    counts["archive_errors"] += 1
                    log(reason="archive_error", error=str(exc))
                db.commit()
                counts["distinct_pages"] = db.execute(
                    "SELECT count(DISTINCT id) FROM revisions"
                ).fetchone()[0]
                counts["ever_published_pages"] = len(published_ids)
                for ident, revision, member, line in db.execute(
                    "SELECT id,revision,member,line FROM revisions r WHERE revision < (SELECT max(revision) FROM revisions WHERE id=r.id) ORDER BY id,revision"
                ):
                    counts["superseded_revisions"] += 1
                    log(
                        reason="superseded_revision",
                        document_id=str(ident),
                        revision_id=str(revision),
                        member=member,
                        line=line,
                    )
                rejected, dates = Counter(), Counter()
                lengths, sample_candidates = [], []
                with (stage / "articles.ndjson").open(
                    "w", encoding="utf-8", newline="\n"
                ) as articles:
                    for ident, revision, payload, member, line in db.execute(
                        "SELECT id,revision,payload,member,line FROM revisions r WHERE revision=(SELECT max(revision) FROM revisions WHERE id=r.id) ORDER BY id"
                    ):
                        record = json.loads(payload)
                        reason = exclusion(record)
                        if reason:
                            rejected[reason] += 1
                            log(
                                reason=reason,
                                document_id=str(ident),
                                revision_id=str(revision),
                                member=member,
                                line=line,
                            )
                            sample_candidates.append(
                                {"id": str(ident), "group": "excluded", "reason": reason}
                            )
                            continue
                        body, sources, pubdate, status, evidence = clean_html(
                            record["article_body"]["html"]
                        )
                        if not body:
                            rejected["empty_body"] += 1
                            log(
                                reason="empty_body",
                                document_id=str(ident),
                                member=member,
                                line=line,
                            )
                            sample_candidates.append(
                                {"id": str(ident), "group": "excluded", "reason": "empty_body"}
                            )
                            continue
                        article = ProcessedArticle(
                            document_id=str(ident),
                            revision_id=str(revision),
                            title=normalized(record["name"]),
                            body=body,
                            url=record["url"],
                            categories=sorted({c["name"] for c in record.get("categories", [])}),
                            publication_date=pubdate,
                            publication_date_status=status,
                            publication_date_evidence=evidence,
                            sources=sources,
                            license=record.get("license", []),
                            provenance={
                                "snapshot_id": SNAPSHOT,
                                "input_sha256": source_hash,
                                "member": member,
                                "line": line,
                            },
                        )
                        articles.write(canonical(article.model_dump(mode="json")) + "\n")
                        lengths.append(len(body))
                        dates[status] += 1
                        sample_candidates.append(
                            {
                                "id": str(ident),
                                "group": "kept",
                                "length": len(body),
                                "date_status": status,
                                "sources": bool(sources),
                                "table": "<table" in record["article_body"]["html"],
                            }
                        )
                counts["articles_produced"] = len(lengths)
                counts["pages_excluded"] = sum(rejected.values())
                accounted = (
                    counts["invalid_records"]
                    + counts["identical_duplicate"]
                    + counts["revision_conflict"]
                    + counts["superseded_revisions"]
                    + counts["pages_excluded"]
                    + counts["articles_produced"]
                )
                if accounted != counts["records_read"]:
                    raise ValueError("Record accounting mismatch")
                if not counts["records_read"]:
                    counts["archive_errors"] += 1
                    log(reason="empty_input")
                if checksum(input_path) != source_hash:
                    raise ValueError("Input changed during processing")
                errors = sum(
                    counts[k] for k in ("invalid_records", "revision_conflict", "archive_errors")
                )
                if errors and not audit_only:
                    raise ValueError(
                        "Corpus build failed validation; run corpus audit for diagnostics"
                    )
                ordered = sorted(lengths)
                p99 = ordered[max(0, math.ceil(len(ordered) * 0.99) - 1)] if ordered else 0
                anomalies = [
                    s
                    for s in sample_candidates
                    if s["group"] == "kept" and (s["length"] < 100 or s["length"] > p99)
                ]

                def stable(s):
                    return hashlib.sha256(s["id"].encode()).hexdigest()

                kept = sorted([s for s in sample_candidates if s["group"] == "kept"], key=stable)
                excluded = sorted(
                    [s for s in sample_candidates if s["group"] == "excluded"], key=stable
                )
                review = kept[:20] + excluded[:10]
                selected = {s["id"] for s in review}
                # Two examples per critical stratum, then deterministic fill.
                critical = []
                for predicate in (
                    lambda s: s["table"],
                    lambda s: s["sources"],
                    lambda s: s["date_status"] != "validated",
                    lambda s: s["length"] < 100,
                    lambda s: s["length"] > p99,
                ):
                    choices = [s for s in kept if s["id"] not in selected and predicate(s)][:2]
                    critical.extend(choices)
                    selected.update(s["id"] for s in choices)
                critical.extend([s for s in kept if s["id"] not in selected][: 10 - len(critical)])
                review.extend(critical)
                audit = {
                    "counts": dict(counts),
                    "excluded_by_reason": dict(rejected),
                    "date_status": dict(dates),
                    "lengths": {
                        "min": min(lengths, default=0),
                        "max": max(lengths, default=0),
                        "p99": p99,
                    },
                    "anomalies": anomalies,
                    "review_sample": review,
                    "valid": not errors,
                }
                (stage / "audit.json").write_text(canonical(audit) + "\n", encoding="utf-8")
            if audit_only:
                (stage / "articles.ndjson").unlink()
            artifacts = {
                p.name: checksum(p) for p in stage.iterdir() if p.suffix in {".json", ".ndjson"}
            }
            manifest = {
                "snapshot_id": SNAPSHOT,
                "input_filename": input_path.name,
                "input_sha256": source_hash,
                "pipeline_version": PIPELINE_VERSION,
                "pipeline_source_sha256": checksum(__file__),
                "selection_version": "1",
                "cleaning_version": "1",
                "mode": "audit" if audit_only else "build",
                "valid": not errors,
                "counts": dict(counts),
                "artifacts": artifacts,
                "destination_index": None,
                "execution": {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "git": git_info(),
                    "dependencies": {
                        name: importlib.metadata.version(name)
                        for name in ("beautifulsoup4", "lxml", "pydantic")
                    },
                },
            }
            (stage / "manifest.json").write_text(canonical(manifest) + "\n", encoding="utf-8")
        finally:
            db.close()
        (stage / "records.sqlite").unlink()
        if output_path.exists():
            output_path.rmdir()
        stage.rename(output_path)
    return manifest
