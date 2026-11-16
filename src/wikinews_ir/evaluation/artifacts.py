"""Atomic artifact directories and portable checksums."""

import hashlib
import json
import tempfile
from datetime import UTC, datetime
from pathlib import Path


def sha(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def file_sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def jsonl(rows):
    return "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)


def read_rows(path):
    return [json.loads(line) for line in Path(path).read_text("utf-8").splitlines() if line.strip()]


def write_bundle(output, kind, files, metadata=None):
    output = Path(output)
    if output.exists():
        raise ValueError("La directory di output esiste già")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent, prefix=".benchmark-") as temp:
        staging = Path(temp) / "result"
        staging.mkdir()
        hashes = {}
        for name, content in files.items():
            if Path(name).name != name:
                raise ValueError("Nome artefatto non valido")
            (staging / name).write_text(content, encoding="utf-8", newline="\n")
            hashes[name] = file_sha(staging / name)
        manifest = {
            "schema_version": "1", "kind": kind, "metadata": metadata or {},
            "artifacts": hashes, "execution": {"created_at": datetime.now(UTC).isoformat()},
        }
        (staging / "manifest.json").write_text(encoded(manifest), encoding="utf-8")
        staging.rename(output)
    return manifest


def verify_bundle(directory, kind=None):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text("utf-8"))
    if kind and manifest["kind"] != kind:
        raise ValueError("Tipo di artefatto incompatibile")
    for name, digest in manifest["artifacts"].items():
        if Path(name).name != name or file_sha(directory / name) != digest:
            raise ValueError(f"Checksum errato: {name}")
    return manifest
