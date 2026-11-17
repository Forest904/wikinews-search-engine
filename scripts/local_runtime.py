"""Windows local development lifecycle. Invoked by the PowerShell entry points."""
from __future__ import annotations

import argparse
import contextlib
import ipaddress
import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "output" / "local"
STATE = RUNTIME / "state.json"
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"


def powershell(code):
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", code],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def processes():
    raw = powershell("Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,ExecutablePath,CommandLine,@{n='Created';e={$_.CreationDate.ToUniversalTime().ToString('o')}} | ConvertTo-Json -Compress")
    return json.loads(raw or "[]")


def owned(process):
    command = (process.get("CommandLine") or "").lower()
    executable = (process.get("ExecutablePath") or "").lower()
    return (
        executable == str(PYTHON).lower()
        and "uvicorn" in command
        and "wikinews_ir.api.main:app" in command
    )


def listeners(port):
    raw = powershell(f"@(Get-NetTCPConnection -State Listen -LocalPort {port} -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique) | ConvertTo-Json -Compress")
    result = json.loads(raw or "[]")
    return result if isinstance(result, list) else [result]


def read_state():
    if not STATE.exists():
        return None
    return json.loads(STATE.read_text(encoding="utf-8"))


def stop_instance(port):
    snapshot = processes()
    state = read_state()
    targets = []
    if state:
        if state.get("root") != str(ROOT):
            raise RuntimeError("Lo stato locale appartiene a un'altra checkout.")
        for process in snapshot:
            if process["ProcessId"] == state["pid"] and process["Created"] == state["created"]:
                if not owned(process):
                    raise RuntimeError("Identita del processo salvato non confermata.")
                targets.append(process)
    # Resolve listeners through their parent chain (reload workers are child processes).
    by_id = {p["ProcessId"]: p for p in snapshot}
    for pid in listeners(port):
        current = by_id.get(pid)
        visited = set()
        match = None
        while current and current["ProcessId"] not in visited:
            visited.add(current["ProcessId"])
            if owned(current):
                match = current
            current = by_id.get(current["ParentProcessId"])
        if match is None:
            raise RuntimeError(f"Porta {port} occupata dal PID {pid}: progetto non identificabile. Nessun processo terminato.")
        targets.append(match)
    for target in {p["ProcessId"]: p for p in targets}.values():
        # Recheck creation time immediately before terminating, guarding against PID reuse.
        fresh = next((p for p in processes() if p["ProcessId"] == target["ProcessId"]), None)
        if not fresh or fresh["Created"] != target["Created"]:
            continue
        if not owned(fresh):
            raise RuntimeError("Identita del processo cambiata prima dell'arresto.")
        subprocess.run(["taskkill", "/PID", str(target["ProcessId"]), "/T", "/F"], check=True, capture_output=True)
        print(f"Istanza locale arrestata (PID {target['ProcessId']}).")
    deadline = time.monotonic() + 15
    ports = {port, state["port"]} if state else {port}
    while any(listeners(p) for p in ports):
        if time.monotonic() >= deadline:
            raise RuntimeError("La porta non si e liberata dopo l'arresto.")
        time.sleep(.3)
    STATE.unlink(missing_ok=True)
    if not targets:
        print("Nessuna istanza locale da arrestare.")


def probe(url):
    try:
        with urllib.request.urlopen(url, timeout=2) as response:
            return response.status == 200
    except (urllib.error.URLError, TimeoutError, OSError):
        return False


def configuration():
    config = {**dotenv_values(ROOT / ".env"), **os.environ}
    url = config.get("ELASTICSEARCH_URL") or "http://127.0.0.1:9200"
    parsed = urlsplit(url)
    try:
        local = parsed.hostname == "localhost" or ipaddress.ip_address(parsed.hostname).is_loopback
    except ValueError:
        local = False
    if not local or parsed.scheme not in {"http", "https"} or parsed.username or parsed.password:
        raise RuntimeError("ELASTICSEARCH_URL deve indicare localhost o un IP loopback, senza credenziali nell'URL.")
    env = dict(os.environ)
    for key, value in config.items():
        if value is not None:
            env[key] = value
    env["ELASTICSEARCH_URL"] = url
    env["ANNOTATION_DB"] = str(ROOT / "data" / "annotation" / "annotation.sqlite3")
    env["ANNOTATION_COOKIE_SECURE"] = "0"
    return env, parsed


def run(command, env):
    subprocess.run(command, cwd=ROOT, env=env, check=True)


def ensure_docker(env, timeout=120):
    """Start Desktop when needed and wait for the engine, not just its GUI."""
    def ready(wait):
        try:
            return subprocess.run(
                ["docker", "info"], env=env, capture_output=True,
                timeout=wait, check=False,
            ).returncode == 0
        except FileNotFoundError:
            raise RuntimeError("Docker non trovato. Installa Docker Desktop e riapri VS Code.") from None
        except subprocess.TimeoutExpired:
            return False

    if ready(5):
        return
    print("Docker non pronto: avvio Docker Desktop e attendo il motore...", flush=True)
    launch_code = """
$ErrorActionPreference = 'Stop'
if (-not (Get-Process -Name 'Docker Desktop' -ErrorAction SilentlyContinue)) {
    $candidates = @(
        "$env:ProgramFiles\\Docker\\Docker\\Docker Desktop.exe",
        "$env:LOCALAPPDATA\\Programs\\DockerDesktop\\Docker Desktop.exe"
    )
    $desktop = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $desktop) { throw 'Docker Desktop non trovato. Installalo o avvialo manualmente e riprova.' }
    Start-Process -FilePath $desktop -WindowStyle Hidden
}
"""
    try:
        powershell(launch_code)
    except subprocess.CalledProcessError as error:
        detail = (error.stderr or error.stdout or str(error)).strip()
        raise RuntimeError(f"Avvio Docker Desktop fallito: {detail}") from None
    deadline = time.monotonic() + timeout
    while (remaining := deadline - time.monotonic()) > 0:
        if ready(min(5, remaining)):
            print("Docker pronto.", flush=True)
            return
        time.sleep(min(2, max(0, deadline - time.monotonic())))
    raise RuntimeError(f"Docker non pronto dopo {timeout} secondi. Controlla Docker Desktop e riprova.")


def start(args):
    env, elastic = configuration()
    if args.mock:
        env["ELASTICSEARCH_INDEX"] = "wikinews_demo_standard_v1"
        env["ELASTICSEARCH_ITALIAN_INDEX"] = "wikinews_demo_italian_v1"
    stop_instance(args.port)
    try:
        with socket.create_connection((elastic.hostname, elastic.port or 9200), timeout=2):
            pass
    except OSError:
        es_port = int(env.get("ES_PORT", "9200"))
        if (elastic.port or 9200) != es_port:
            raise RuntimeError("ES_PORT e la porta di ELASTICSEARCH_URL non coincidono.") from None
        ensure_docker(env)
        try:
            run(["docker", "compose", "--project-directory", str(ROOT), "--env-file", str(ROOT / ".env"), "-f", str(ROOT / "compose.yaml"), "up", "-d", "--wait", "elasticsearch"], env)
        except (FileNotFoundError, subprocess.CalledProcessError):
            raise RuntimeError("Avvio Elasticsearch fallito. Controlla l'errore Docker Compose riportato sopra.") from None
    run([str(PYTHON), "-m", "wikinews_ir.cli", "annotation", "init"], env)
    if args.mock:
        run([str(PYTHON), "-m", "wikinews_ir.cli", "seed-demo"], env)
        run([str(PYTHON), str(ROOT / "scripts/local_mock.py")], env)
    stdout = RUNTIME / "app.stdout.log"
    stderr = RUNTIME / "app.stderr.log"
    with stdout.open("ab") as out, stderr.open("ab") as err:
        process = subprocess.Popen(
            [str(PYTHON), "-m", "uvicorn", "wikinews_ir.api.main:app", "--app-dir", str(ROOT / "src"), "--host", "127.0.0.1", "--port", str(args.port), "--reload", "--reload-dir", str(ROOT / "src")],
            cwd=ROOT, env=env, stdout=out, stderr=err, stdin=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
    identity = next((p for p in processes() if p["ProcessId"] == process.pid), None)
    if not identity:
        raise RuntimeError(f"Applicazione terminata all'avvio. Log: {stderr}")
    STATE.write_text(json.dumps({"root": str(ROOT), "pid": process.pid, "created": identity["Created"], "port": args.port}), encoding="utf-8")
    base = f"http://127.0.0.1:{args.port}"
    deadline = time.monotonic() + 45
    while not probe(base + "/api/health/live"):
        if process.poll() is not None or time.monotonic() >= deadline:
            stop_instance(args.port)
            raise RuntimeError(f"Applicazione non pronta. Log: {stderr}")
        time.sleep(.4)
    print(f"Sito locale pronto: {base}")
    print(f"Log: {stdout} e {stderr}")
    if not probe(base + "/api/ready"):
        print("Ricerca non pronta. Controlla Elasticsearch; per preparare gli indici: uv run --locked wikinews-ir index build")
    print("Database locale: data/annotation/annotation.sqlite3. Per il primo account: uv run --locked wikinews-ir annotation create-user coordinatore --coordinator")
    route = {"ricerca": "/", "valutazione": "/annotate", "coordinamento": "/coordinate"}[args.page]
    if not args.no_browser:
        webbrowser.open(base + route)


@contextlib.contextmanager
def lock():
    import msvcrt
    RUNTIME.mkdir(parents=True, exist_ok=True)
    with (RUNTIME / "lifecycle.lock").open("a+b") as handle:
        handle.seek(0)
        if not handle.read(1):
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        except OSError:
            raise RuntimeError("Un altro avvio/arresto locale e gia in corso.") from None
        try:
            yield
        finally:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["start", "stop", "status"])
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--page", choices=["ricerca", "valutazione", "coordinamento"], default="ricerca")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--mock", action="store_true", help="Indici sintetici e pacchetto UI mock locale")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("Porta fuori intervallo")
    try:
        with lock():
            if args.action == "start":
                start(args)
            elif args.action == "stop":
                stop_instance(args.port)
            else:
                state = read_state()
                port = state["port"] if state else args.port
                base = f"http://127.0.0.1:{port}"
                print(f"Indirizzo locale: {base}")
                print(f"PID registrato: {state['pid'] if state else 'nessuno'}")
                for label, route in [("Applicazione", "/api/health/live"), ("Ricerca", "/api/ready"), ("Valutazione", "/api/health/annotation")]:
                    print(f"{label}: {'pronto' if probe(base + route) else 'non disponibile'}")
        return 0
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"Errore: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
