"""Benchmark CLI; all network operations require explicit --live."""

import json
from pathlib import Path


def configure(subparsers):
    parser = subparsers.add_parser("benchmark", help="Benchmark offline e silver Codex")
    commands = parser.add_subparsers(dest="benchmark_command", required=True)

    def command(name, fields=()):
        p = commands.add_parser(name)
        for field in fields:
            p.add_argument("--" + field, type=Path, required=True)
        return p

    command("validate", ("topics", "protocol"))
    command("pilot-report", ("source", "output")).add_argument("--coordinator-review", type=Path)
    command("budget", ("report", "plan", "output"))
    command("freeze", ("plan", "output"))
    command("reconcile-pilot", ("pilot", "corpus", "output"))
    command("queries", ("topics", "protocol", "output"))
    p = command("external-run", ("topics", "corpus", "output"))
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--replay", type=Path)
    mode.add_argument("--live", action="store_true")
    p.add_argument("--top-k", type=int, default=100)
    p.add_argument("--user-agent")
    p = command("pool", ("topics", "corpus", "output"))
    p.add_argument("--runs", nargs="+", type=Path, required=True)
    p = command("select", ("pool", "output"))
    p.add_argument("--quotas", type=Path, help="JSON object run_id -> quota per topic")
    p.add_argument("--seed", type=int)
    p.add_argument("--exclude-pairs", type=Path)
    command("packet", ("topics", "protocol", "selection", "corpus", "output"))
    p = command("export-qrels", ("packet", "judgments", "output"))
    p.add_argument("--source", choices=("gold", "silver"), required=True)
    p = command("silver")
    silver = p.add_subparsers(dest="silver_command", required=True)
    for name in ("prepare", "validate", "import"):
        s = silver.add_parser(name)
        s.add_argument("--packet", type=Path, required=True)
        if name != "prepare":
            s.add_argument("--judgments", type=Path, required=True)
        if name != "validate":
            s.add_argument("--output", type=Path, required=True)
        if name == "prepare":
            s.add_argument("--batch-id", required=True)
        elif name == "validate":
            s.add_argument("--allow-partial", action="store_true")
        else:
            s.add_argument("--operator", required=True)
            s.add_argument("--execution-id", required=True)
            s.add_argument("--model", default="unknown")
            s.add_argument("--prior-output", nargs="*", type=Path, default=[])


def dispatch(args):
    from wikinews_ir.evaluation import benchmark as b
    from wikinews_ir.evaluation import silver as s

    cmd = args.benchmark_command
    if cmd in {"pilot-report", "budget", "freeze"}:
        from wikinews_ir.evaluation import pilot
        if cmd == "pilot-report":
            return pilot.pilot_report(args.source, args.output, args.coordinator_review)
        if cmd == "budget":
            return pilot.budget(args.report, args.plan, args.output)
        return pilot.freeze(args.plan, args.output)
    if cmd == "validate":
        topics, protocol = b.load_topics(args.topics), b.load_protocol(args.protocol)
        return {"valid": True, "topics": len(topics), "protocol": protocol}
    if cmd == "reconcile-pilot":
        return b.reconcile(args.pilot, args.corpus, args.output)
    if cmd == "queries":
        return b.queries(args.topics, args.protocol, args.output)
    if cmd == "external-run":
        from wikinews_ir.adapters.wikimedia import external_run
        return external_run(args.topics, args.corpus, args.output, args.top_k,
                            args.replay, args.user_agent)
    if cmd == "pool":
        return b.pool(args.topics, args.corpus, args.runs, args.output)
    if cmd == "select":
        quotas = json.loads(args.quotas.read_text("utf-8")) if args.quotas else None
        return b.select(args.pool, args.output, quotas, args.seed, args.exclude_pairs)
    if cmd == "packet":
        return b.packet(args.topics, args.protocol, args.selection, args.corpus, args.output)
    if cmd == "export-qrels":
        return s.export_qrels(args.packet, args.judgments, args.output, args.source)
    if args.silver_command == "prepare":
        return s.prepare(args.packet, args.output, args.batch_id)
    if args.silver_command == "validate":
        return s.validate_silver(args.packet, args.judgments, args.allow_partial)
    return s.import_silver(args.packet, args.judgments, args.output, args.operator,
                           args.execution_id, args.model, args.prior_output)
