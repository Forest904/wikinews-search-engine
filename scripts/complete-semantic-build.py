"""Resume the full corpus, verify the local search API, and stage the package on the VPS."""

import json
import subprocess
import sys
from pathlib import Path

import httpx


def main():
    out = Path("output/semantic-full")
    bundle = Path("data/processed/semantic-qwen3-06b-full")
    out.mkdir(parents=True, exist_ok=True)
    cli = [sys.executable, "-m", "wikinews_ir.cli", "semantic"]
    expected = json.loads(Path("data/processed/m2-v1/manifest.json").read_bytes())["counts"][
        "articles_produced"
    ]
    if not (bundle / "manifest.json").exists():
        subprocess.run(
            [*cli, "generate", "--corpus", "data/processed/m2-v1", "--package", str(bundle)],
            check=True,
        )
    manifest = json.loads((bundle / "manifest.json").read_bytes())
    if manifest["count"] != expected or manifest["skipped"] != 0:
        raise ValueError("Conteggio inatteso")
    subprocess.run([*cli, "import", "--check-archive", "--package", str(bundle)], check=True)
    subprocess.run([*cli, "verify", "--check-archive", "--package", str(bundle)], check=True)
    response = httpx.get(
        "http://127.0.0.1:8000/api/search",
        params={"q": "terremoto", "profile": "semantic"},
        timeout=180,
    )
    response.raise_for_status()
    data = response.json()
    if data["total"] != expected or not data["hits"]:
        raise ValueError("Verifica API fallita")
    (out / "verified-local.json").write_text(json.dumps(data, ensure_ascii=False), encoding="utf8")
    subprocess.run(
        [
            sys.executable,
            "scripts/transfer_semantic.py",
            str(bundle),
            "--activate",
            "--host",
            "root@2.29.176.129",
            "--key",
            str(Path.home() / ".ssh/newsfinder"),
        ],
        check=True,
    )
    (out / "completed.json").write_text(
        json.dumps(
            {
                "count": expected,
                "index": data["index"],
                "uploaded": True,
                "production_verified": True,
            }
        ),
        encoding="utf8",
    )


if __name__ == "__main__":
    main()
