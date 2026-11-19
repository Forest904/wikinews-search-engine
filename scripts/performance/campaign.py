"""Orchestrate k6 and retain input parameters, raw metrics and threshold results."""

import argparse
import json
import os
import platform
import subprocess
import time
from pathlib import Path

import httpx
from engine import checksum, write_json

SCRIPT = Path(__file__).with_name("web.js")


def measure(args, label, rate, duration, mode):
    raw = args.output / (label + ".json.gz")
    summary = args.output / (label + "-summary.json")
    env = dict(
        os.environ,
        BASE_URL=args.url,
        MODE=mode,
        MIX=args.mix,
        RATE=str(rate),
        DURATION=duration,
        ERROR_BUDGET=str(args.error_budget),
    )
    if args.p95_ms is not None:
        env["P95_MS"] = str(args.p95_ms)
    info = dict(
        start=time.time(),
        url=args.url,
        mode=mode,
        mix=args.mix,
        rate=rate,
        duration=duration,
        script_sha256=checksum(SCRIPT),
        generator=platform.platform(),
        commit=subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        k6=subprocess.check_output([args.k6, "version"], text=True).strip(),
        topology=args.topology,
        options={
            k: env.get(k)
            for k in ("QUERIES", "FOLDERS", "SEMANTIC_PERCENT", "VUS", "ERROR_BUDGET", "P95_MS")
        },
    )
    dest = args.output / (label + "-manifest.json")
    if args.mix != "annotation":
        ready = httpx.get(args.url.rstrip("/") + "/api/ready", timeout=20)
        info["readiness_status"] = ready.status_code
        if ready.is_success:
            info["indices"] = ready.json()["profiles"]
    for key in ("ORACLE", "ACCOUNTS"):
        if key in env:
            path = Path(env[key]).resolve(strict=True)
            env[key] = path.as_posix()
            if key == "ORACLE":
                info["oracle_sha256"] = checksum(path)
    write_json(dest, info)
    result = subprocess.run(
        [
            args.k6,
            "run",
            "--quiet",
            "--out",
            "json=" + str(raw),
            "--summary-export",
            str(summary),
            str(SCRIPT),
        ],
        env=env,
        check=False,
    )
    info.update(end=time.time(), exit_code=result.returncode)
    write_json(dest, info)
    if result.returncode not in (0, 99) or not summary.is_file():
        raise RuntimeError("k6 failed to execute; inspect the run output")
    metrics = json.loads(summary.read_text("utf-8"))["metrics"]
    started = metrics.get("journeys_started", {}).get("count", 0)
    completed = metrics.get("iterations", {}).get("count", 0)
    passed = result.returncode == 0 and started > 0 and completed == started
    info.update(
        started=started,
        completed=completed,
        dropped=metrics.get("dropped_iterations", {}).get("count", 0),
        passed=passed,
    )
    write_json(dest, info)
    return passed


def campaign(args):
    if args.mode != "capacity":
        return measure(args, args.mode, args.rate, args.duration, args.mode)
    low, high = 0, args.rate
    while high <= args.max_rate and measure(args, "step-" + str(high), high, "5m", "step"):
        low, high = high, high * 2
    if high > args.max_rate:
        if low != args.max_rate and not measure(args, "ceiling", args.max_rate, "5m", "step"):
            high = args.max_rate
        else:
            ok = measure(args, "confirm-ceiling", args.max_rate, "15m", "step")
            write_json(
                args.output / "capacity.json",
                dict(tested_ceiling=args.max_rate, confirmed=ok, saturation_observed=False),
            )
            return ok
    while high - low > 1:
        middle = (low + high) // 2
        if measure(args, "refine-" + str(middle), middle, "5m", "step"):
            low = middle
        else:
            high = middle
    sustainable = bool(low) and measure(args, "confirm-pass", low, "15m", "step")
    exceeded = not measure(args, "confirm-fail", high, "15m", "step")
    write_json(
        args.output / "capacity.json",
        dict(
            last_pass=low,
            first_failure=high,
            pass_confirmed=sustainable,
            failure_confirmed=exceeded,
        ),
    )
    return sustainable and exceeded


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output", type=Path)
    p.add_argument("--url", required=True)
    p.add_argument(
        "--topology", required=True, help="Replica, worker, limits, generator and network"
    )
    p.add_argument(
        "--mode", choices=["capacity", "step", "baseline", "spike", "soak"], default="step"
    )
    p.add_argument(
        "--mix",
        choices=["lexical", "mixed", "filter", "archive", "live", "annotation"],
        default="lexical",
    )
    p.add_argument("--rate", type=int, default=1)
    p.add_argument("--max-rate", type=int, default=64)
    p.add_argument("--duration")
    p.add_argument("--p95-ms", type=float)
    p.add_argument("--error-budget", type=float, default=0)
    p.add_argument("--k6", default="k6")
    args = p.parse_args()
    if args.duration is None:
        args.duration = "2h" if args.mode == "soak" else "5m"
    if (
        args.rate < 1
        or not 0 <= args.error_budget < 1
        or (args.mode == "capacity" and (args.p95_ms is None or args.max_rate < args.rate))
    ):
        p.error("Capacity needs --p95-ms and a valid rate interval")
    args.output.mkdir(parents=True, exist_ok=False)
    raise SystemExit(int(not campaign(args)))
