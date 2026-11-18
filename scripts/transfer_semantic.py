"""Stage an archive-checked Qdrant import package on the project's VPS."""

import argparse
import json
import shlex
import subprocess
import tarfile
import tempfile
import uuid
from pathlib import Path

from wikinews_ir.ingestion.corpus import checksum
from wikinews_ir.semantic_cli import package_rows

REMOTE = "/opt/newsfinder/imports"


def transfer(package, host, key):
    manifest = json.loads((package / "manifest.json").read_bytes())
    if manifest["limit"] or manifest["selection"] or manifest["variant"] != "natural":
        raise ValueError("Specificare il pacchetto naturale del corpus completo")
    # Validate every source batch before sending any data.
    for _ in package_rows(package, manifest):
        pass
    identifier = checksum(package / "manifest.json")
    target = f"{REMOTE}/semantic-{identifier[:16]}"
    options = ["-o", "BatchMode=yes", "-o", "StrictHostKeyChecking=yes", "-i", str(key)]

    def remote(command, **kwargs):
        return subprocess.run(["ssh", *options, "--", host, command], check=True, **kwargs)

    names = ["config.json", "manifest.json"] + [
        f"batch-{index:06}.json" for index in range(len(manifest["batches"]))
    ]
    # Use a unique staging directory so failed or concurrent uploads cannot replace an index.
    stage = f"{REMOTE}/.semantic-{uuid.uuid4().hex}"
    with tempfile.TemporaryDirectory() as tmp:
        archive = Path(tmp) / "package.tar.gz"
        with tarfile.open(archive, "w:gz", compresslevel=1) as stream:
            for name in names:
                stream.add(package / name, arcname=name, recursive=False)
        remote(f"mkdir -m 700 {stage}")
        subprocess.run(
            ["scp", *options, "--", str(archive), f"{host}:{stage}/package.tar.gz"], check=True
        )
        # Verify the compressed transfer before extraction and every batch on disk afterwards.
        verify = r"""
import hashlib, json, os, sys, tarfile
from pathlib import Path
stage, target = map(Path, sys.argv[1:3])
def sha(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()
archive = stage / "package.tar.gz"
if sha(archive) != sys.argv[3]:
    raise ValueError("Checksum trasferimento errato")
with tarfile.open(archive) as bundle:
    bundle.extractall(stage, filter="data")
def check(directory):
    if sha(directory/"manifest.json") != sys.argv[4]:
        raise ValueError("Manifest remoto diverso")
    manifest = json.loads((directory/"manifest.json").read_bytes())
    for i, expected in enumerate(manifest["batches"]):
        if sha(directory/f"batch-{i:06}.json") != expected:
            raise ValueError(f"Batch remoto danneggiato: {i}")
check(stage)
archive.unlink()
if target.exists():
    check(target)
    for item in stage.iterdir():
        item.unlink()
    stage.rmdir()
else:
    os.rename(stage, target)
print(target)
"""
        remote(shlex.join(["python3", "-c", verify, stage, target, checksum(archive), identifier]))

    return target


def activate_remote(package, target, host, key):
    manifest = json.loads((package / "manifest.json").read_bytes())
    script = Path(__file__).resolve().parents[1] / "deploy" / "activate-semantic.sh"
    command = shlex.join(
        ["bash", "-s", "--", "/imports/" + target.rsplit("/", 1)[1], str(manifest["count"])]
    )
    subprocess.run(
        [
            "ssh",
            "-o",
            "BatchMode=yes",
            "-o",
            "StrictHostKeyChecking=yes",
            "-i",
            str(key),
            host,
            command,
        ],
        input=script.read_bytes().replace(b"\r\n", b"\n"),
        check=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("package", type=Path)
    parser.add_argument("--host", required=True)
    parser.add_argument("--key", type=Path, required=True)
    parser.add_argument("--activate", action="store_true")
    args = parser.parse_args()
    target = transfer(args.package, args.host, args.key)
    if args.activate:
        activate_remote(args.package, target, args.host, args.key)
