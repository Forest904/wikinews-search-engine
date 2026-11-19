"""Pause one named replica dependency during a running workload, then restore it."""

import argparse
import json
import subprocess
import time
from pathlib import Path

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("container", help="Exact container name on the disposable replica")
    p.add_argument("output", type=Path)
    p.add_argument("--seconds", type=int, default=30)
    p.add_argument("--before", type=int, default=60)
    args = p.parse_args()
    if args.seconds <= 0 or args.before < 0:
        p.error("Invalid time interval")

    def inspect():
        return json.loads(subprocess.check_output(["docker", "inspect", args.container]))[0]

    info = inspect()
    if (
        info["Name"].lstrip("/") != args.container
        or not info["State"]["Running"]
        or info["State"]["Paused"]
    ):
        raise ValueError("Expected an exact, running, unpaused container")
    with args.output.open("x", encoding="utf-8", buffering=1) as log:

        def mark(event):
            log.write(json.dumps(dict(event=event, epoch=time.time(), container=info["Id"])) + "\n")

        mark("baseline")
        time.sleep(args.before)
        subprocess.run(["docker", "pause", info["Id"]], check=True)
        try:
            mark("paused")
            time.sleep(args.seconds)
        finally:
            subprocess.run(["docker", "unpause", info["Id"]], check=True)
            mark("restored")
