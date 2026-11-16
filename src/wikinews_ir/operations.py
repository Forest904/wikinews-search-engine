"""Readiness and coherent, disk-free server snapshots for deployment operations."""

import argparse
import os
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

from wikinews_ir.annotation import database_path


def open_existing(path, mode="ro"):
    return sqlite3.connect(Path(path).resolve().as_uri() + f"?mode={mode}", uri=True, timeout=2)


def check_annotation(path):
    # Never initialize or migrate a database from a monitoring request.
    with closing(open_existing(path, "rw")) as db:
        if db.execute("PRAGMA user_version").fetchone()[0] != 2:
            raise ValueError("Unsupported schema")
        db.execute("SELECT id FROM users LIMIT 1")
        db.execute("SELECT id FROM timing LIMIT 1")
        db.execute("BEGIN IMMEDIATE")
        db.execute("UPDATE users SET coordinator=coordinator WHERE 0")
        db.rollback()


def snapshot(path):
    with closing(open_existing(path)) as source, closing(sqlite3.connect(":memory:")) as target:
        source.backup(target)
        if target.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
            raise ValueError("Snapshot integrity failure")
        if target.execute("PRAGMA user_version").fetchone()[0] != 2:
            raise ValueError("Unsupported schema")
        return target.serialize()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["snapshot", "check"])
    parser.add_argument("--db", default=database_path())
    args = parser.parse_args()
    if args.command == "check":
        check_annotation(args.db)
    else:
        payload = snapshot(args.db)
        if os.name == "nt":
            import msvcrt
            msvcrt.setmode(sys.stdout.fileno(), os.O_BINARY)
        sys.stdout.buffer.write(payload)


if __name__ == "__main__":
    main()
