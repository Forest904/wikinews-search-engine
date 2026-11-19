"""Sample Docker CPU, memory, network and block I/O with wall-clock timestamps."""

import argparse
import json
import platform
import subprocess
import time
from pathlib import Path

from wikinews_ir.retrieval.engine import RetrievalEngine

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output", type=Path)
    p.add_argument("containers", nargs="*")
    p.add_argument(
        "--host", action="store_true", help="Sample generator CPU/RAM/network with psutil"
    )
    p.add_argument("--seconds", type=int, default=900)
    p.add_argument("--interval", type=int, default=5)
    p.add_argument("--es", action="store_true")
    args = p.parse_args()
    if not (args.host or args.containers or args.es) or min(args.seconds, args.interval) < 1:
        p.error("Select a resource source and positive time intervals")
    if args.host:
        import psutil

        psutil.cpu_percent()
    end = time.monotonic() + args.seconds
    backend = RetrievalEngine() if args.es else None
    try:
        with args.output.open("x", encoding="utf-8") as f:
            while time.monotonic() < end:
                result = (
                    subprocess.check_output(
                        [
                            "docker",
                            "stats",
                            "--no-stream",
                            "--format",
                            "{{json .}}",
                            *args.containers,
                        ],
                        text=True,
                    )
                    if args.containers
                    else ""
                )
                now = time.time()
                if args.host:
                    net = psutil.net_io_counters()
                    f.write(
                        json.dumps(
                            dict(
                                epoch=now,
                                host=platform.node(),
                                cpu_percent=psutil.cpu_percent(),
                                available_bytes=psutil.virtual_memory().available,
                                bytes_sent=net.bytes_sent,
                                bytes_received=net.bytes_recv,
                            )
                        )
                        + "\n"
                    )
                for line in result.splitlines():
                    row = dict(json.loads(line), epoch=now)
                    f.write(json.dumps(row) + "\n")
                if backend:
                    stats = backend.client.nodes.stats(metric="jvm,thread_pool").body
                    for node in stats["nodes"].values():
                        f.write(
                            json.dumps(
                                dict(
                                    epoch=now,
                                    node=node["name"],
                                    jvm=node["jvm"],
                                    search=node["thread_pool"]["search"],
                                )
                            )
                            + "\n"
                        )
                f.flush()
                time.sleep(max(0, min(args.interval, end - time.monotonic())))
    finally:
        if backend:
            backend.close()
