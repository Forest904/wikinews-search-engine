"""Offline evaluation over graded qrels and the exported rank order."""

import csv
from collections import defaultdict
from html import escape
from importlib.metadata import version
from io import StringIO
from statistics import mean

import ir_measures as ir

from .artifacts import file_sha, write_bundle
from .benchmark import load_topics
from .report_inputs import load_labels, load_rankings

MEASURES = {"nDCG@10": ir.nDCG@10, "P@5": ir.P(rel=1)@5, "MRR@10": ir.RR(rel=1)@10}


def tsv(rows, fields):
    stream = StringIO()
    writer = csv.DictWriter(stream, fields, delimiter="\t", lineterminator="\n")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: "N/D" if v is None else v for k, v in row.items()})
    return stream.getvalue()


def agreement(gold, silver):
    matrix = [[0] * 3 for _ in range(3)]
    differences = []
    for q, d in sorted(gold.keys() & silver.keys()):
        a, b = gold[q, d], silver[q, d]
        matrix[a][b] += 1
        if a != b:
            differences.append(dict(query_id=q, document_id=d, gold=a, silver=b))
    rows = list(map(sum, matrix))
    cols = list(map(sum, zip(*matrix, strict=True)))
    n = sum(rows)
    f1 = mean(2 * matrix[i][i] / (rows[i] + cols[i]) if rows[i] + cols[i] else 0
              for i in range(3)) if n else None
    observed = sum(abs(i-j) * matrix[i][j] for i in range(3) for j in range(3))
    expected = sum(abs(i-j) * rows[i] * cols[j] for i in range(3) for j in range(3))
    kappa = 1 - observed * n / expected if expected else None
    return matrix, differences, dict(shared=n, macro_F1=f1, linear_kappa=kappa)


def evaluate_run(tag, ranking, source, grades, abstained, topics):
    qrels = defaultdict(dict)
    for (qid, doc), grade in grades.items():
        qrels[qid][doc] = grade
    scores = defaultdict(dict)
    if qrels:
        run = {qid: {doc: -i for i, doc in enumerate(ranking[qid])} for qid in qrels}
        for result in ir.iter_calc(list(MEASURES.values()), dict(qrels), run):
            scores[result.query_id][result.measure] = result.value
    rows, coverage = [], []
    for qid, topic in topics.items():
        base = dict(run=tag, source=source, query_id=qid)
        row = dict(**base, status="valutabile" if qid in qrels else "senza gradi validi")
        for name, measure in MEASURES.items():
            eligible = qid in qrels and (name != "MRR@10" or topic["type"] == "event-specific")
            row[name] = scores[qid][measure] if eligible else None
        rows.append(row)
        for k in (5, 10):
            docs = ranking[qid][:k]
            judged = sum((qid, d) in grades for d in docs)
            coverage.append(dict(**base, k=k, returned=len(docs), judged=judged,
                                 unjudged=len(docs)-judged,
                                 abstained=sum((qid, d) in abstained for d in docs)
                                 if abstained is not None else None,
                                 coverage=judged/len(docs) if docs else None))
    return rows, coverage


def coverage_svg(groups):
    width = max(520, max(len(label) for label, _ in groups) * 9 + 270)
    svg = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" '
           f'height="{40 + 26 * len(groups)}" font-family="sans-serif" font-size="14">',
           '<title>Copertura aggregata sui risultati restituiti</title>',
           '<text x="10" y="20">Copertura sui risultati restituiti</text>']
    for i, (label, value) in enumerate(groups):
        y = 46 + i * 26
        svg.append(f'<text x="10" y="{y}">{escape(label)}</text>')
        if value is not None:
            svg.append(f'<rect x="{width-230}" y="{y-12}" width="{160*value:.2f}" '
                       'height="13" fill="#23776f"/>')
        display = "N/D" if value is None else f"{value:.1%}"
        svg.append(f'<text x="{width-65}" y="{y}">{display}</text>')
    return "\n".join([*svg, "</svg>"])


def evaluate(topics_path, split, runs, output, gold=None, silver=None, fixture=False):
    sources = {k: v for k, v in (("gold", gold), ("silver", silver)) if v is not None}
    if not sources:
        raise ValueError("Specificare almeno una fonte tra --gold e --silver")
    topics = load_topics(topics_path)
    chosen = {t["query_id"]: t for t in topics if t["split"] == split}
    if not chosen:
        raise ValueError("Nessun topic nello split")
    rankings = {}
    for directory in runs:
        for tag, ranking in load_rankings(directory, topics):
            if tag in rankings:
                raise ValueError("Identificativo run duplicato")
            rankings[tag] = ranking
    metadata = dict(split=split, fixture=fixture, ir_measures=version("ir-measures"),
                    topics=str(topics_path), topics_sha256=file_sha(topics_path),
                    run_manifests={str(p): file_sha(p/"manifest.json") for p in runs},
                    sources={}, relevance_threshold=1, cutoffs=[5, 10], denominators={})
    title = "Valutazione sintetica (fixture)" if fixture else "Valutazione retrieval"
    report = [f"# {title}", "", f"Split **{split}**, {len(chosen)} topic.",
              "", "| Run | Fonte | Metrica | Media | Topic inclusi |",
              "|---|---|---|---:|---:|"]
    metrics, summaries, coverage, bars, labels = [], [], [], [], {}
    notes = []
    for source, directory in sources.items():
        grades, abstained, total = load_labels(directory, source, {t["query_id"] for t in topics},
                                              chosen.keys(), split)
        labels[source] = grades
        metadata["sources"][source] = dict(path=str(directory),
                                           manifest_sha256=file_sha(directory/"manifest.json"),
                                           bundle_abstentions=total)
        detail = "identificabili per coppia" if abstained is not None else "solo totale del bundle"
        notes.append(f"- {source}: {total} astensioni nell’export ({detail}).")
        for tag, ranking in rankings.items():
            rows, counts = evaluate_run(tag, ranking, source, grades, abstained, chosen)
            metrics.extend(rows)
            coverage.extend(counts)
            denominators = metadata["denominators"].setdefault(source, {})
            for name in MEASURES:
                values = [r[name] for r in rows if r[name] is not None]
                value = mean(values) if values else None
                denominators[name] = len(values)
                summaries.append(dict(run=tag, source=source, metric=name, mean=value,
                                      topics=len(values)))
                display = "N/D" if value is None else f"{value:.4f}"
                report.append(f"| {tag} | {source} | {name} | {display} | {len(values)} |")
            for k in (5, 10):
                subset = [r for r in counts if r["k"] == k]
                returned = sum(r["returned"] for r in subset)
                bars.append((f"{tag} / {source} @{k}",
                             sum(r["judged"] for r in subset)/returned if returned else None))
    report.extend(["", "P@5 usa grado ≥ 1 e denominatore 5. MRR@10 usa la stessa soglia "
                   "sui topic event-specific. Le medie escludono i topic senza gradi validi.",
                   "Gli unjudged conservano la posizione nel ranking e hanno guadagno nullo.",
                   "", *notes, "", "![Copertura aggregata](coverage.svg)"])
    files = {"metrics.tsv": tsv(metrics, metrics[0]), "summary.tsv": tsv(summaries, summaries[0]),
             "coverage.tsv": tsv(coverage, coverage[0]), "coverage.svg": coverage_svg(bars)}
    if len(labels) == 2:
        matrix, differences, stats = agreement(labels["gold"], labels["silver"])
        metadata["agreement"] = stats
        files["disagreements.tsv"] = tsv(differences, ["query_id", "document_id", "gold", "silver"])
        report.extend(["", "## Accordo gold/silver", "", "| Gold / Silver | 0 | 1 | 2 |",
                       "|---|---:|---:|---:|"])
        report.extend(f"| {i} | {row[0]} | {row[1]} | {row[2]} |" for i, row in enumerate(matrix))
        files["confusion.tsv"] = tsv([dict(zip(["gold", "0", "1", "2"], [i, *row], strict=True))
                                      for i, row in enumerate(matrix)], ["gold", "0", "1", "2"])
        report.extend(["", f"Coppie condivise: {stats['shared']}."])
        for key in ("macro_F1", "linear_kappa"):
            value = stats[key]
            reason = "intersezione vuota" if not stats["shared"] else "disaccordo atteso nullo"
            report.append(f"- {key}: " + (f"{value:.4f}" if value is not None else f"N/D ({reason})"))
    files["report.md"] = "\n".join(report) + "\n"
    return write_bundle(output, "evaluation-report", files, metadata)
