"""Pilot evidence, person-hour budgets and immutable production freeze."""

import json
import math
import tempfile
from collections import Counter, defaultdict
from itertools import combinations
from pathlib import Path
from statistics import median

from wikinews_ir.evaluation.artifacts import (
    encoded,
    file_sha,
    read_rows,
    verify_bundle,
    write_bundle,
)
from wikinews_ir.evaluation.benchmark import load_topics
from wikinews_ir.evaluation.silver import validate_payload


def stats(values):
    values = sorted(values)
    return {"n": len(values), "median": median(values) if values else None,
            "p75": values[math.ceil(.75 * len(values)) - 1] if values else None}


def pilot_report(source, output):
    source = Path(source)
    manifest = verify_bundle(source, "annotation-gold-export")
    if not {"packet.json", "assignments.jsonl", "history.jsonl", "timing.jsonl",
            "discussions.jsonl", "source_manifest.json"} <= manifest["artifacts"].keys():
        raise ValueError("Export privo degli artefatti pilot verificabili")
    packet = json.loads((source / "packet.json").read_text("utf-8"))
    validate_payload(packet)
    if any(t["split"] != "calibration" for t in packet["topics"]):
        raise ValueError("Il report pilot accetta solo calibrazione")
    assignments = read_rows(source / "assignments.jsonl")
    history = read_rows(source / "history.jsonl")
    timing = read_rows(source / "timing.jsonl")
    discussions = read_rows(source / "discussions.jsonl")
    source_manifest = json.loads((source / "source_manifest.json").read_text("utf-8")) or {}
    latest = {}
    def key(r):
        return r["query_id"], r["document_id"], r["user_id"]
    for row in sorted(history, key=lambda r: r["version"]):
        latest[key(row)] = row
    completed = {k: r for k, r in latest.items() if r["status"] != "deferred"}
    duration, groups = defaultdict(float), defaultdict(list)
    for row in timing:
        duration[(*key(row), row["phase"])] += row["seconds"]
    for (qid, did, user, phase), seconds in duration.items():
        for group in (f"phase:{phase}", f"topic:{qid}:{phase}", f"user:{user}:{phase}"):
            groups[group].append(seconds)
    annotation_seconds = []
    missing = []
    for row in assignments:
        k = key(row)
        if k not in completed or any((*k, phase) not in duration for phase in ("reading", "annotation")):
            missing.append(list(k))
        else:
            annotation_seconds.append(sum(duration[(*k, phase)] for phase in ("reading", "annotation")))
    agreement = {}
    users = sorted({r["user_id"] for r in assignments})
    for a, b in combinations(users, 2):
        pairs = [(r, completed.get((q, d, b))) for (q, d, u), r in completed.items() if u == a]
        graded = [(x["grade"], y["grade"]) for x, y in pairs if y and
                  x["status"] == y["status"] == "judged"]
        agreement[f"{a}/{b}"] = {"graded_pairs": len(graded),
                                  "agreements": sum(x == y for x, y in graded),
                                  "disagreements": sum(x != y for x, y in graded)}
    discussion_seconds = sum(r["minutes"] * 60 * len(json.loads(r["participants"]))
                             for r in discussions)
    per_user = {u: sum(r["seconds"] for r in timing if r["user_id"] == u) +
                sum(r["minutes"] * 60 for r in discussions if u in json.loads(r["participants"]))
                for u in users}
    pairs = Counter((r["query_id"], r["document_id"]) for r in assignments)
    complete = (len(packet["topics"]) == 4 and len({t["type"] for t in packet["topics"]}) == 4
                and len(pairs) == len(packet["pairs"]) == 24
                and set(pairs.values()) == {3} and len(users) == 3
                and len(completed) == len(assignments) == 72 and not missing
                and bool(discussions) and all(r["notes"].strip() and r["minutes"] > 0 for r in discussions))
    report = {"kind": "measured-pilot", "ready_for_freeze": complete,
              "fixture": bool(manifest["metadata"].get("fixture")) or bool(
                  source_manifest.get("metadata", {}).get("fixture")) or any(
                  d["revision_id"].startswith("fixture") for d in packet["documents"]),
              "distinct_pairs": len(pairs), "assignments": len(assignments),
              "completed": len(completed), "missing_timing": missing,
              "incomplete_segments": sum(not r["complete"] for r in timing),
              "abstentions": sum(r["status"] == "needs_review" for r in completed.values()),
              "agreement": agreement, "duration_groups": {k: stats(v) for k, v in groups.items()},
              "annotation_seconds": stats(annotation_seconds),
              "consumed_person_seconds": sum(r["seconds"] for r in timing) + discussion_seconds,
              "consumed_seconds_per_user": per_user,
              "calibration_families": sorted({t["event_family"] for t in packet["topics"]}),
              "calibration_pairs": packet["pairs"],
              "source_manifest_sha256": file_sha(source / "manifest.json")}
    if report["incomplete_segments"]:
        report["ready_for_freeze"] = False
    files = {"report.json": encoded(report),
             "source__manifest.json": (source / "manifest.json").read_text("utf-8")}
    for name in manifest["artifacts"]:
        files["source__" + name] = (source / name).read_text("utf-8")
    return write_bundle(output, "pilot-report", files)


def budget(report_dir, plan_path, output):
    verify_bundle(report_dir, "pilot-report")
    report = json.loads((Path(report_dir) / "report.json").read_text("utf-8"))
    plan = json.loads(Path(plan_path).read_text("utf-8"))
    p75 = report["annotation_seconds"]["p75"]
    if not p75 or not report["ready_for_freeze"]:
        raise ValueError("Misure complete del pilot richieste")
    pairs, double = plan["distinct_pairs"], plan["double_pairs"]
    reserve = plan["review_reserve_minutes"]
    loads = plan["annotations_per_user"]
    if (type(pairs) is not int or type(double) is not int or not 0 <= double <= pairs
            or pairs <= 0 or not isinstance(reserve, (int, float)) or not math.isfinite(reserve)
            or reserve <= 0 or len(loads) != 3 or sum(loads.values()) != pairs + double
            or any(type(n) is not int or n < 0 for n in loads.values())):
        raise ValueError("Piano budget non valido")
    required = report["consumed_person_seconds"] + reserve * 60 + (pairs + double) * p75
    if set(loads) != set(report["consumed_seconds_per_user"]):
        raise ValueError("Gli utenti del budget devono corrispondere al pilot")
    total_user = {u: (n * p75 + report["consumed_seconds_per_user"][u] + reserve * 60 / 3) / 3600
                  for u, n in loads.items()}
    result = {"plan": plan, "p75_seconds": p75, "required_person_hours": required / 3600,
              "production_hours_per_user": {u: n * p75 / 3600 for u, n in loads.items()},
              "total_hours_per_user": total_user,
              "scenarios": [{"hours": h, "fits": required <= h * 3600 and
                             all(v <= h / 3 for v in total_user.values()),
                             "remaining_seconds": h * 3600 - required} for h in (12, 15, 18)],
              "pilot_manifest_sha256": file_sha(Path(report_dir) / "manifest.json")}
    return write_bundle(output, "pilot-budget", {"budget.json": encoded(result)})


def freeze(plan_path, output):
    """References are relative to the plan; all evidence is copied into a self-contained bundle."""
    plan_path = Path(plan_path)
    plan = json.loads(plan_path.read_text("utf-8"))
    root = plan_path.parent
    required = {"version", "pilot", "budget", "topics", "calibration_topics", "packet",
                "pool", "selection", "local_run", "external_run", "assignments", "prompt",
                "model", "top_k", "quotas", "seed", "hours", "semantic_overlap_review"}
    if not required <= plan.keys() or not plan["semantic_overlap_review"].strip():
        raise ValueError("Piano incompleto: richiesti tutti gli artefatti e revisione delle famiglie")
    paths = {k: root / plan[k] for k in required - {
        "version", "model", "top_k", "quotas", "seed", "hours", "semantic_overlap_review"}}
    manifests = {k: verify_bundle(paths[k]) for k in
                 ("pilot", "budget", "packet", "pool", "selection", "local_run", "external_run")}
    if any(manifests[k].get("kind") != kind for k, kind in {
        "pilot": "pilot-report", "budget": "pilot-budget", "packet": "packet", "pool": "pool",
        "selection": "selection", "external_run": "external-run"}.items()):
        raise ValueError("Tipo artefatto errato")
    report = json.loads((paths["pilot"] / "report.json").read_text("utf-8"))
    estimate = json.loads((paths["budget"] / "budget.json").read_text("utf-8"))
    if (not report["ready_for_freeze"] or report["fixture"] or
            estimate["pilot_manifest_sha256"] != file_sha(paths["pilot"] / "manifest.json") or
            not any(s["hours"] == plan["hours"] and s["fits"] for s in estimate["scenarios"])):
        raise ValueError("Pilot reale e budget sostenibile richiesti")
    topics = load_topics(paths["topics"])
    calibration = load_topics(paths["calibration_topics"])
    splits = Counter(t["split"] for t in topics)
    if splits != {"development": 24, "test": 16} or any(
        sum(t["type"] == typ for t in topics) != 10 for typ in
        ("event-specific", "topical", "entity-oriented", "multi-constraint")
    ):
        raise ValueError("Richiesti 40 topic, 10 per tipo, split 24/16")
    families = set(report["calibration_families"]) | {t["event_family"] for t in calibration}
    if any(t["event_family"] in families for t in topics):
        raise ValueError("Famiglia di calibrazione nella produzione")
    packet = json.loads((paths["packet"] / "packet.json").read_text("utf-8"))
    validate_payload(packet)
    if sorted(packet["topics"], key=lambda t: t["query_id"]) != sorted(topics, key=lambda t: t["query_id"]):
        raise ValueError("Topic del pacchetto incompatibili")
    assignments = read_rows(paths["assignments"])
    available = {(p["query_id"], p["document_id"]) for p in packet["pairs"]}
    calibration_docs = {p["document_id"] for p in report.get("calibration_pairs", [])}
    test_ids = {t["query_id"] for t in topics if t["split"] == "test"}
    if any(q in test_ids and d in calibration_docs for q, d in available):
        raise ValueError("Documento di calibrazione nel test")
    seen = set()
    counts = Counter()
    for a in assignments:
        key = (a["query_id"], a["document_id"], a["user_id"])
        if key in seen or key[:2] not in available:
            raise ValueError("Assegnazione duplicata o fuori pacchetto")
        seen.add(key)
        counts[key[:2]] += 1
    covered = {k[0] for k in counts}
    if (not {t["query_id"] for t in topics if t["split"] == "test"} <= covered
            or not any(t["split"] == "development" and t["query_id"] in covered for t in topics)
            or not set(counts.values()) <= {1, 2}):
        raise ValueError("Copertura gold o doppie letture non valide")
    bp = estimate["plan"]
    if (len(counts) != bp["distinct_pairs"] or sum(v == 2 for v in counts.values()) != bp["double_pairs"]
            or dict(Counter(a["user_id"] for a in assignments)) != bp["annotations_per_user"]):
        raise ValueError("Assegnazioni incompatibili con budget")
    selection, pool = manifests["selection"]["metadata"], manifests["pool"]["metadata"]
    if (set(plan["quotas"]) != set(pool["run_ids"]) or
            any(type(n) is not int or n < 0 for n in plan["quotas"].values()) or
            type(plan["seed"]) is not int):
        raise ValueError("Quote intere per tutte le run e seed intero richiesti")
    if (selection["pool_manifest_sha256"] != file_sha(paths["pool"] / "manifest.json") or
            manifests["packet"]["metadata"]["selection_manifest_sha256"] != file_sha(paths["selection"] / "manifest.json")
            or pool["topics_sha256"] != file_sha(paths["topics"]) or
            selection["quotas"] != plan["quotas"] or selection["seed"] != plan["seed"]):
        raise ValueError("Catena pool/selezione/pacchetto incompatibile")
    if set(manifests["local_run"]["profiles"]) != {"E0", "E1", "E2", "E3", "E4"}:
        raise ValueError("Richieste tutte le run E0–E4")
    wanted = {t["query_id"]: t["query"] for t in topics}
    external = manifests["external_run"]["metadata"]
    if (external["top_k"] != plan["top_k"] or not external["complete"]
            or external["queries"] != wanted or external["corpus"] != pool["corpus"]
            or manifests["packet"]["metadata"]["corpus"] != pool["corpus"]
            or set(pool["inputs"].values()) != {
                file_sha(paths["local_run"] / "manifest.json"),
                file_sha(paths["external_run"] / "manifest.json")}):
        raise ValueError("Run esterna, corpus o provenienza pool incompatibili")
    for profile, meta in manifests["local_run"]["profiles"].items():
        records = [r for r in manifests["local_run"]["queries"] if r["profile"] == profile]
        if ({r["query_id"]: r["query"] for r in records} != wanted or
                any(meta.get(k) != v for k, v in pool["corpus"].items())):
            raise ValueError("Run locale incompatibile")
    selected = read_rows(paths["selection"] / "selection.jsonl")
    pool_pairs = {(r["query_id"], r["document_id"]): r
                  for r in read_rows(paths["pool"] / "pool.jsonl")}
    if not available <= pool_pairs.keys():
        raise ValueError("Selezione fuori pool")
    if {(r["query_id"], r["document_id"]) for r in selected} != available:
        raise ValueError("Coppie selezionate diverse dal pacchetto")
    documents = {d["document_id"]: d for d in packet["documents"]}
    for row in selected:
        if any(row[k] != documents[row["document_id"]][k] for k in ("body_sha256", "revision_id")):
            raise ValueError("Testi selezionati diversi dal pacchetto")
        if any(row[k] != pool_pairs[row["query_id"], row["document_id"]][k]
               for k in ("body_sha256", "revision_id")):
            raise ValueError("Selezione incompatibile col pool")
    if manifests["local_run"]["top_k"] != plan["top_k"] or not plan["model"].strip():
        raise ValueError("Profondità o modello non dichiarati")
    if not paths["prompt"].read_text("utf-8").strip():
        raise ValueError("Prompt vuoto")
    packet["protocol"].update(version=plan["version"], status="frozen")
    validate_payload(packet)
    files = {"plan.json": encoded(plan), "packet.json": encoded(packet)}
    for name, path in paths.items():
        if path.is_dir():
            for file in sorted(path.iterdir()):
                if file.is_file():
                    files[f"{name}__{file.name}"] = file.read_text("utf-8")
        else:
            files[f"{name}__{path.name}"] = path.read_text("utf-8")
    output = Path(output)
    if output.exists():
        raise ValueError("Output già esistente")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as temp:
        staging = Path(temp) / "freeze"
        archive = write_bundle(staging / "archive", "benchmark-freeze", files,
                               {"version": plan["version"]})
        write_bundle(staging / "packet", "packet", {
            "packet.json": encoded(packet), "PROMPT.md": paths["prompt"].read_text("utf-8")},
            {"corpus": pool["corpus"], "model": plan["model"],
             "freeze_manifest_sha256": file_sha(staging / "archive" / "manifest.json")})
        staging.rename(output)
    return archive
