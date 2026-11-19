"""Generate quality/latency, capacity and recovery figures from retained samples."""

import argparse
import gzip
import json
import random
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from engine import TOPICS, checksum, distribution, records, write_json

from wikinews_ir.evaluation.report import MEASURES, evaluate_run
from wikinews_ir.evaluation.report_inputs import load_labels


def quality(args):
    run = args.engine
    manifest = json.loads((run / "manifest.json").read_text("utf-8"))
    if checksum(args.topics) != manifest["topics_sha256"]:
        raise ValueError("Topic file changed")
    all_topics = records(args.topics)
    topics = {t["query_id"]: t for t in all_topics if t["split"] == manifest["split"]}
    samples = records(run / "samples.jsonl")
    completed = json.loads((run / "summary.json").read_text("utf-8"))
    if completed["errors"]:
        raise ValueError("Engine run failed")
    if any(s["error"] for s in samples):
        raise ValueError("Incomplete run contains failed searches")
    rankings, times = defaultdict(dict), defaultdict(list)
    for s in samples:
        if s["iteration"] and s["category"] == "topic":
            p, q = s["profile"], s["case"]
            if rankings[p].setdefault(q, s["ranking"]) != s["ranking"]:
                raise ValueError(f"Unstable ranking for {p}/{q}")
            times[p].append(s["ms"])
    target = len(topics) * manifest["sessions"] * manifest["repeats"]
    if (
        "E1" not in rankings
        or set(rankings) != set(manifest["profiles"])
        or any(set(v) != set(topics) for v in rankings.values())
        or any(len(v) != target for v in times.values())
    ):
        raise ValueError("Missing baseline or incomplete topic coverage")
    for source in ("gold", "silver"):
        bundle = getattr(args, source)
        if not bundle:
            continue
        grades, abstained, _ = load_labels(
            bundle, source, {t["query_id"] for t in all_topics}, set(topics), manifest["split"]
        )
        scores, summary, pool = {}, {}, set()
        fig, ax = plt.subplots(layout="constrained")
        for p, ranking in rankings.items():
            rows, coverage = evaluate_run(p, ranking, source, grades, abstained, topics)
            scores[p] = {r["query_id"]: r for r in rows}
            metrics = {}
            for name in MEASURES:
                vals = [r[name] for r in rows if r[name] is not None]
                metrics[name] = mean(vals) if vals else None
            coverage = [r for r in coverage if r["k"] == 10]
            pool.update((q, d) for q in ranking for d in ranking[q][:10] if (q, d) not in grades)
            p95 = distribution(times[p])["p95"]
            summary[p] = dict(metrics=metrics, p95_ms=p95, coverage=coverage)
            if metrics["nDCG@10"] is not None:
                ax.scatter(p95, metrics["nDCG@10"])
                ax.annotate(p, (p95, metrics["nDCG@10"]))
        for p, rows in scores.items():
            delta = {
                q: r["nDCG@10"] - scores["E1"][q]["nDCG@10"]
                for q, r in rows.items()
                if r["nDCG@10"] is not None
            }
            if not delta:
                raise ValueError("No eligible topics")
            vals = list(delta.values())
            rng = random.Random(manifest["seed"])
            estimates = sorted(mean(rng.choices(vals, k=len(vals))) for _ in range(5000))
            summary[p].update(
                delta_by_topic=delta,
                delta_mean=mean(vals),
                ci95=[estimates[124], estimates[4874]],
                improved=sum(x > 0 for x in vals),
                tied=vals.count(0),
                worse=sum(x < 0 for x in vals),
            )
        ax.set(xlabel="Latenza p95 del motore (ms)", ylabel="nDCG@10", title=source)
        fig.savefig(args.output / f"quality-{source}.png")
        plt.close(fig)
        write_json(
            args.output / f"quality-{source}.json",
            dict(
                summary=summary,
                topics=scores,
                qrels_manifest_sha256=checksum(bundle / "manifest.json"),
                unjudged=sorted(pool),
            ),
        )


def web(args):
    fig, axes = plt.subplots(3, 1, sharex=True, layout="constrained")
    timeline, tax = plt.subplots(2, 1, sharex=True, layout="constrained")
    groups = defaultdict(list)
    breakdown = defaultdict(list)
    statuses = defaultdict(int)
    rows = []
    for path in args.web:
        buckets = defaultdict(lambda: defaultdict(list))
        opener = gzip.open if path.suffix == ".gz" else open
        with opener(path, "rt", encoding="utf-8-sig") as stream:
            for line in stream:
                item = json.loads(line)
                if item["type"] != "Point" or item["metric"] not in {
                    "journeys_started",
                    "useful_journeys",
                    "journey_failed",
                    "journey_ms",
                    "dropped_iterations",
                    "http_reqs",
                    "http_req_duration",
                }:
                    continue
                data = item["data"]
                metric = item["metric"]
                if metric == "http_reqs":
                    tags = data["tags"]
                    statuses[
                        str(path), tags.get("name"), tags.get("status"), tags.get("error_code")
                    ] += int(data["value"])
                if metric in ("http_req_duration", "journey_ms", "journey_failed"):
                    tags = data["tags"]
                    breakdown[
                        str(path),
                        tags.get("scenario"),
                        metric,
                        tags.get("name") or tags.get("profile"),
                    ].append(data["value"])
                if metric == "http_req_duration":
                    continue
                stamp = datetime.fromisoformat(data["time"].replace("Z", "+00:00")).timestamp()
                bucket = buckets[data["tags"].get("scenario", ""), int(stamp) // 10]
                bucket[item["metric"]].append(data["value"])
        # Only full interior windows contribute to the capacity curve.
        for scenario in sorted({s for s, _ in buckets}):
            windows = sorted(t for s, t in buckets if s == scenario)
            in_flight = 0
            for t in range(windows[0], windows[-1] + 1):
                b = buckets[scenario, t]
                dist = distribution(b["journey_ms"])
                in_flight += sum(b["journeys_started"]) - dist["n"]
                row = dict(
                    file=str(path),
                    phase=scenario,
                    epoch=t * 10,
                    offered_rps=(sum(b["journeys_started"]) + sum(b["dropped_iterations"])) / 10,
                    useful_rps=sum(b["useful_journeys"]) / 10,
                    http_rps=sum(b["http_reqs"]) / 10,
                    errors=sum(b["journey_failed"]),
                    dropped=sum(b["dropped_iterations"]),
                    in_flight_end=in_flight,
                    **dist,
                )
                rows.append(row)
                if t in (windows[0], windows[-1]):
                    continue
                g = groups[str(path), scenario]
                g.append((row, b["journey_ms"], b["journey_failed"]))
            points = [
                r for r in rows if r["file"] == str(path) and r["phase"] == scenario and r["n"]
            ]
            tax[0].plot(
                [r["epoch"] for r in points], [r["p95"] for r in points], label=path.stem + scenario
            )
    for (path, scenario), g in groups.items():
        x = mean(r["offered_rps"] for r, _, _ in g)
        delays = [v for _, vs, _ in g for v in vs]
        errors = [v for _, _, vs in g for v in vs]
        if delays and errors:
            for ax, y in zip(
                axes,
                [
                    mean(r["useful_rps"] for r, _, _ in g),
                    distribution(delays)["p95"],
                    100 * mean(errors),
                ],
                strict=True,
            ):
                ax.scatter(x, y)
                ax.annotate(Path(path).stem + " " + scenario, (x, y), fontsize=7)
    for ax, label in zip(axes, ["Percorsi validi/s", "p95 (ms)", "Errori (%)"], strict=True):
        ax.set_ylabel(label)
    axes[-1].set_xlabel("Arrivi offerti (percorsi/s)")
    if args.resources:
        containers = defaultdict(list)
        for rec in records(args.resources):
            if "CPUPerc" not in rec:
                continue
            containers[rec["Name"]].append((rec["epoch"], float(rec["CPUPerc"].strip("%"))))
        for name, points in containers.items():
            tax[1].plot(*zip(*points), label=name)
        tax[1].legend(fontsize=6)
    tax[0].set_ylabel("p95 (ms)")
    if args.fault:
        for event in records(args.fault):
            if event["event"] in ("paused", "restored"):
                tax[0].axvline(event["epoch"], color="grey", linestyle="--")
                tax[0].annotate(event["event"], (event["epoch"], 0))
    tax[1].set(xlabel="Unix time (s)", ylabel="CPU container (%)")
    fig.savefig(args.output / "capacity.png")
    timeline.savefig(args.output / "recovery.png")
    plt.close("all")
    write_json(args.output / "windows.json", rows)
    write_json(
        args.output / "http-status.json",
        [
            dict(file=file, endpoint=endpoint, status=status, error_code=code, count=count)
            for (file, endpoint, status, code), count in statuses.items()
        ],
    )
    write_json(
        args.output / "breakdown.json",
        [
            dict(
                file=file,
                scenario=scenario,
                metric=metric,
                group=group,
                **(
                    {"n": len(values), "error_fraction": mean(values)}
                    if metric == "journey_failed"
                    else distribution(values)
                ),
            )
            for (file, scenario, metric, group), values in breakdown.items()
        ],
    )


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output", type=Path)
    p.add_argument("--engine", type=Path)
    p.add_argument("--topics", type=Path, default=TOPICS)
    for source in ("gold", "silver", "resources", "fault"):
        p.add_argument("--" + source, type=Path)
    p.add_argument("--web", type=Path, nargs="+")
    args = p.parse_args()
    if not (args.web or (args.engine and (args.gold or args.silver))):
        p.error("Supply --web or --engine with a judgment bundle")
    args.output.mkdir(parents=True, exist_ok=False)
    if args.engine:
        quality(args)
    if args.web:
        web(args)
