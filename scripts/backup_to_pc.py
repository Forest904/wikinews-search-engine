"""Download SQLite over SSH without remote backup files or shell binary redirection."""

import argparse
import hashlib
import os
import re
import sqlite3
import subprocess
from contextlib import closing
from pathlib import Path


def download(host, destination):
    if not re.fullmatch(r"[A-Za-z0-9_.@-]+", host) or host.startswith("-"):
        raise ValueError("Use an SSH config alias or user@hostname")
    destination = Path(destination).resolve()
    partial = destination.with_name(destination.name + ".partial")
    if destination.exists():
        raise ValueError("Destination already exists")
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = ("cd /opt/newsfinder/current && sudo -n bash scripts/server.sh compose "
               "exec -T app python -m wikinews_ir.operations snapshot")
    # stderr stays on the terminal; only the raw SQLite stream goes to the file.
    with partial.open("xb") as output:
        subprocess.run(["ssh", "-T", host, command], stdout=output, check=True)
        output.flush()
        os.fsync(output.fileno())
    with closing(sqlite3.connect(partial.as_uri() + "?mode=ro", uri=True)) as db:
        if db.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Downloaded database is corrupt")
        if db.execute("PRAGMA user_version").fetchone()[0] != 2:
            raise ValueError("Unsupported database schema")
    # Hard link is atomic, fails if destination exists, and never overwrites another copy.
    os.link(partial, destination)
    partial.unlink()
    digest = hashlib.sha256(destination.read_bytes()).hexdigest()
    print(f"Verified: {destination}\nSHA-256: {digest}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("host", help="SSH alias or user@hostname; configure key authentication first")
    parser.add_argument("destination", type=Path, help="New local .sqlite3 file")
    args = parser.parse_args()
    download(args.host, args.destination)
