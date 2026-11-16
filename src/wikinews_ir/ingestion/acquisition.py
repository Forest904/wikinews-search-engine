"""Acquire the pinned course snapshot, then prepare or verify its corpus."""

import hashlib
import importlib.metadata
import json
import tempfile
import time
from pathlib import Path

import httpx

from wikinews_ir.ingestion import corpus

FILENAME = "itwikinews-NS0-20250320-ENTERPRISE-HTML.json.tar.gz"
URL = "https://dumps.wikimedia.org/other/enterprise_html/runs/20250320/" + FILENAME
SHA256 = "d2c00ef9d7c3db5a3f26adb85b07055673b30b2417653374ada52b7174df474d"
SIZE = 72975193
USER_AGENT = "WikinewsIR/0.1 (academic corpus acquisition; Python httpx)"
ARTIFACTS = ("articles.ndjson", "audit.json", "decisions.ndjson")


def _https_only(request):
    if request.url.scheme != "https":
        raise ValueError("Download e redirect devono usare HTTPS")


def acquire(raw_dir):
    """Return a verified archive; never replace an existing mismatched file."""
    directory = Path(raw_dir).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / FILENAME
    if destination.exists():
        print(f"Verifica archivio locale: {destination}", flush=True)
        if (
            not destination.is_file()
            or destination.stat().st_size != SIZE
            or corpus.checksum(destination) != SHA256
        ):
            raise ValueError(f"Archivio locale diverso dallo snapshot atteso: {destination}")
        print("Archivio verificato; riuso senza rete.", flush=True)
        return destination

    print(f"Acquisizione: {URL}", flush=True)
    with httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept-Encoding": "identity"},
        timeout=httpx.Timeout(60, connect=15),
        follow_redirects=True,
        event_hooks={"request": [_https_only]},
    ) as client:
        for attempt in range(3):
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(
                    dir=directory, prefix=".download-", suffix=".part", delete=False
                ) as output:
                    temporary = Path(output.name)
                    digest = hashlib.sha256()
                    size = 0
                    with client.stream("GET", URL) as response:
                        response.raise_for_status()
                        for chunk in response.iter_raw():
                            size += len(chunk)
                            if size > SIZE:
                                raise ValueError("Download più grande dello snapshot atteso")
                            output.write(chunk)
                            digest.update(chunk)
                if size != SIZE or digest.hexdigest() != SHA256:
                    raise ValueError(
                        "Download non valido: dimensione o SHA-256 diverso dal riferimento"
                    )
                if destination.exists():
                    raise ValueError("Archivio comparso durante il download; ripetere la verifica")
                temporary.rename(destination)
                print(f"Download e SHA-256 verificati: {destination}", flush=True)
                return destination
            except httpx.HTTPError as exc:
                retry = (
                    isinstance(exc, httpx.TransportError)
                    or isinstance(exc, httpx.HTTPStatusError)
                    and (exc.response.status_code == 429 or exc.response.status_code >= 500)
                )
                if not retry or attempt == 2:
                    raise ValueError(f"Acquisizione fallita: {exc}") from exc
                delay = 2**attempt
                print(f"Errore temporaneo; nuovo tentativo tra {delay}s.", flush=True)
                time.sleep(delay)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)


def verified_manifest(output):
    """Validate compatibility and hashes before reusing a populated directory."""
    try:
        manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
        expected = {
            "valid": True,
            "mode": "build",
            "snapshot_id": corpus.SNAPSHOT,
            "input_sha256": SHA256,
            "pipeline_version": corpus.PIPELINE_VERSION,
            "pipeline_source_sha256": corpus.checksum(corpus.__file__),
            "selection_version": "1",
            "cleaning_version": "1",
        }
        if any(manifest.get(key) != value for key, value in expected.items()):
            raise ValueError("Manifest incompatibile")
        dependencies = {
            name: importlib.metadata.version(name)
            for name in ("beautifulsoup4", "lxml", "pydantic")
        }
        if manifest["execution"]["dependencies"] != dependencies:
            raise ValueError("Dipendenze di preprocessing diverse")
        for name in ARTIFACTS:
            if corpus.checksum(output / name) != manifest["artifacts"][name]:
                raise ValueError(f"Checksum errato: {name}")
        count = manifest["counts"]["articles_produced"]
        if type(count) is not int or count < 0:
            raise ValueError("Conteggio non valido")
        return manifest
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise ValueError(
            f"Corpus esistente incompleto, alterato o incompatibile ({exc}); scegliere una nuova directory con --output"
        ) from exc


def prepare(raw_dir=Path("data/raw"), output=Path("data/processed/m2-v1")):
    output = Path(output).resolve()
    existing = None
    if output.exists():
        if not output.is_dir():
            raise ValueError("--output deve essere una directory")
        if any(output.iterdir()):
            print(f"Verifica corpus esistente: {output}", flush=True)
            existing = verified_manifest(output)
    archive = acquire(raw_dir)
    if existing is not None:
        print(
            f"Corpus già pronto: {existing['counts']['articles_produced']} articoli in {output}",
            flush=True,
        )
        return existing
    print(f"Preparazione corpus: {output}", flush=True)
    manifest = corpus.run_corpus(archive, output)
    print(
        f"Corpus pronto: {manifest['counts']['articles_produced']} articoli in {output}", flush=True
    )
    return manifest
