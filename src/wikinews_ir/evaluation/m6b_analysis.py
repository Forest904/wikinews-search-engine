"""Paired M6-B analyses. Every aggregate gives each eligible parent topic one vote."""

from collections import defaultdict
from itertools import combinations
from statistics import mean

from wikinews_ir.retrieval.query_builder import parse_phrases

from .report import MEASURES, evaluate_run, tsv

PROFILES = tuple(f"E{i}-v1" for i in range(5))
PAIRS = [(PROFILES[i], PROFILES[j]) for i, j in [(1, 0), (2, 1), (3, 2), (4, 2)]]
PRIMARY = ("nDCG@10", "P@5")


def select_candidate(summary):
    return max(PROFILES, key=lambda run: tuple(summary[run][m] for m in PRIMARY))


def averages(rows):
    result = {}
    for m in MEASURES:
        values = [r[m] for r in rows if r[m] is not None]
        result[m] = mean(values) if values else None
    return result


def scores(run, ranking, grades, topics):
    rows, _ = evaluate_run(run, ranking, "", grades, None, topics)
    return {r["query_id"]: r for r in rows}


def analyze(topics, runs, labels, variants):
    gold, silver = labels["gold"], labels["silver"]
    shared = gold.keys() & silver.keys()
    files, summary, raw = {}, {}, {}
    views = []
    for source, grades in labels.items():
        for view in ("standard", "condensed", "shared"):
            selected = {k: grades[k] for k in shared} if view == "shared" else grades
            for run, ranking in runs.items():
                projected = (
                    {q: [d for d in ranking[q] if (q, d) in grades] for q in topics}
                    if view == "condensed"
                    else ranking
                )
                rows = scores(run, projected, selected, topics)
                avg = averages(rows.values())
                summary[source, view, run] = avg
                if view == "standard" and source == "gold":
                    raw[run] = rows
                for metric, value in avg.items():
                    views.append(
                        dict(
                            source=source,
                            view=view,
                            run=run,
                            metric=metric,
                            mean=value,
                            topics=sum(r[metric] is not None for r in rows.values()),
                        )
                    )
    files["views.tsv"] = tsv(views, views[0])
    comparisons = []
    for left, right in [
        (("gold", "shared"), ("silver", "shared")),
        (("gold", "standard"), ("gold", "condensed")),
        (("silver", "standard"), ("silver", "condensed")),
    ]:
        for a, b in combinations(runs, 2):
            for m in PRIMARY:
                x = summary[*left, a][m] - summary[*left, b][m]
                y = summary[*right, a][m] - summary[*right, b][m]
                change = (
                    "inversione"
                    if x * y < 0
                    else "parita cambiata"
                    if bool(x) != bool(y)
                    else "stabile"
                )
                comparisons.append(
                    dict(
                        first="/".join(left),
                        second="/".join(right),
                        a=a,
                        b=b,
                        metric=m,
                        first_delta=x,
                        second_delta=y,
                        change=change,
                    )
                )
    files["ordering.tsv"] = tsv(comparisons, comparisons[0])
    paired, examples = [], []
    for a, b in PAIRS:
        deltas = []
        for q, topic in topics.items():
            if raw[a][q][PRIMARY[0]] is None:
                continue
            row = dict(
                a=a,
                b=b,
                query_id=q,
                type=topic["type"],
                phrase=("obbligatoria" if parse_phrases(topic["query"])[1] else "boost")
                if a == PROFILES[4]
                else "",
                same_ranking=runs[a][q] == runs[b][q],
            )
            row.update({m: raw[a][q][m] - raw[b][q][m] for m in PRIMARY})
            paired.append(row)
            deltas.append(row)
        for sign, label in [(1, "minimo"), (-1, "massimo")]:
            if not deltas:
                continue
            item = min(deltas, key=lambda r: (sign * r[PRIMARY[0]], r["query_id"]))
            q = item["query_id"]
            examples.append(
                f"### {a} meno {b}, {label}, {q}\n\n{topics[q]['query']} "
                f"(Δ nDCG@10 {item[PRIMARY[0]]:+.4f}).\n"
            )
            for run in (b, a):
                evidence = ", ".join(
                    f"{rank}. {d} ({gold.get((q, d), 'senza giudizio')})"
                    for rank, d in enumerate(runs[run][q][:10], 1)
                )
                examples.append(f"- {run} — {evidence or 'lista vuota'}")
            examples.append("")
    files["paired.tsv"] = tsv(paired, paired[0])
    files["errors.md"] = "# Estremi per ablation sul gold\n\n" + "\n".join(examples)
    typo = []
    for run, var_ranking in variants.items():
        by_parent = defaultdict(list)
        for v, docs in var_ranking.items():
            q = v.split("-")[0]
            if q in topics:
                by_parent[q].append(docs)
        for q, lists in by_parent.items():
            grades = {key: grade for key, grade in gold.items() if key[0] == q}
            values = [scores(run, {q: docs}, grades, {q: topics[q]})[q] for docs in lists]
            avg = averages(values)
            for m in PRIMARY:
                clean = raw[run][q][m]
                typo.append(
                    dict(
                        run=run,
                        query_id=q,
                        variants=len(lists),
                        metric=m,
                        clean=clean,
                        perturbed=avg[m],
                        delta=avg[m] - clean if clean is not None else None,
                        judged_at_10=mean(sum((q, d) in gold for d in docs[:10]) for docs in lists),
                        returned_at_10=mean(len(docs[:10]) for docs in lists),
                    )
                )
    files["typos.tsv"] = tsv(typo, typo[0])
    return files, {r: summary["gold", "standard", r] for r in PROFILES}
