"""Standalone Python 3 validator copied unchanged into Codex workspaces.

Usage: python validate.py --packet . --judgments judgments.jsonl [--allow-partial]
Prints a report; never rewrites input, output, or validation code.
"""

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def rows(path):
    return [json.loads(s) for s in Path(path).read_text("utf-8").splitlines() if s.strip()]


def validate(packet, judgments, allow_partial=False):
    packet = Path(packet)
    errors, normalized = [], []
    manifest = json.loads((packet / "manifest.json").read_text("utf-8"))
    for name, expected in manifest["artifacts"].items():
        if Path(name).name != name or digest(packet / name) != expected:
            errors.append(f"Input modificato: {name}")
    data = json.loads((packet / "packet.json").read_text("utf-8"))
    documents = {d["document_id"]: d for d in data["documents"]}
    expected_pairs = {(p["query_id"], p["document_id"]) for p in data["pairs"]}
    seen, ids = set(), set()
    required = {
        "judgment_id", "query_id", "document_id", "revision_id", "body_sha256",
        "protocol_version", "source", "annotator_id", "judged_at", "status", "grade",
        "rationale", "evidence",
    }
    optional = {"ambiguity_reason", "final", "origin_judgment_ids"}
    try:
        records = rows(judgments)
    except (ValueError, OSError) as exc:
        return {"valid": False, "errors": [*errors, str(exc)], "judgments": []}
    for number, row in enumerate(records, 1):
        try:
            if not isinstance(row, dict) or not required <= row.keys() or (
                row.keys() - required - optional
            ):
                raise ValueError("Campi mancanti o sconosciuti")
            for field in ("judgment_id", "query_id", "document_id", "revision_id",
                          "annotator_id", "protocol_version"):
                value = row[field]
                if not isinstance(value, str) or not value or any(c.isspace() for c in value):
                    raise ValueError(f"Identificativo non valido: {field}")
            pair = row["query_id"], row["document_id"]
            if pair not in expected_pairs or pair in seen or row["judgment_id"] in ids:
                raise ValueError("Coppia inattesa/duplicata o judgment_id duplicato")
            seen.add(pair)
            ids.add(row["judgment_id"])
            doc = documents[row["document_id"]]
            if row["revision_id"] != doc["revision_id"] or (
                row["body_sha256"] != doc["body_sha256"]
            ) or row["protocol_version"] != data["protocol"]["version"]:
                raise ValueError("Revisione, testo o protocollo incompatibile")
            if row["source"] != "codex_chat" or row.get("final", False) is not False or (
                row.get("origin_judgment_ids", []) != []
            ):
                raise ValueError("Fonte silver richiesta; decisione gold non ammessa")
            if datetime.fromisoformat(row["judged_at"]).tzinfo is None:
                raise ValueError("Data senza fuso orario")
            if not isinstance(row["rationale"], str) or not row["rationale"].strip():
                raise ValueError("Motivazione mancante")
            if not isinstance(row["evidence"], list):
                raise ValueError("Evidenze non valide")
            if row["status"] == "judged":
                if type(row["grade"]) is not int or row["grade"] not in (0, 1, 2) or (
                    not row["evidence"]
                ):
                    raise ValueError("Grado o evidenza non valido")
            elif row["status"] == "needs_review":
                if row["grade"] is not None or not isinstance(
                    row.get("ambiguity_reason"), str
                ) or not row["ambiguity_reason"].strip():
                    raise ValueError("Astensione incoerente")
            else:
                raise ValueError("Stato non valido")
            for evidence in row["evidence"]:
                if set(evidence) - {"quote", "field", "start", "end"}:
                    raise ValueError("Campi evidenza sconosciuti")
                quote = evidence["quote"]
                body = doc["body"]
                if evidence.get("field", "body") != "body" or not isinstance(
                    quote, str
                ) or not quote:
                    raise ValueError("Citazione non valida")
                start, end = evidence.get("start"), evidence.get("end")
                if start is None and end is None:
                    start = body.find(quote)
                    if start < 0 or body.find(quote, start + 1) >= 0:
                        raise ValueError("Citazione assente o ambigua: specificare offset")
                    end = start + len(quote)
                if type(start) is not int or type(end) is not int or not (
                    0 <= start < end <= len(body)
                ) or body[start:end] != quote:
                    raise ValueError("Offset/citazione non corrispondono al testo")
                evidence.update(field="body", start=start, end=end)
            normalized.append(row)
        except (ValueError, KeyError, TypeError, AttributeError) as exc:
            errors.append(f"Riga {number}: {exc}")
    missing = sorted(expected_pairs - seen)
    if missing and not allow_partial:
        errors.append(f"Coppie mancanti: {len(missing)}")
    return {"valid": not errors, "errors": errors, "missing": missing,
            "expected": len(expected_pairs), "processed": len(normalized),
            "judgments": normalized}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, default=Path("."))
    parser.add_argument("--judgments", type=Path, required=True)
    parser.add_argument("--allow-partial", action="store_true")
    args = parser.parse_args()
    try:
        report = validate(args.packet, args.judgments, args.allow_partial)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        report = {"valid": False, "errors": [str(exc)]}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["valid"] else 1)


if __name__ == "__main__":
    main()
