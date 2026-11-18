"""Run a loopback-only query relay and reconnect its outgoing SSH tunnel."""
import argparse
import json
import logging
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import httpx
from filelock import FileLock

from wikinews_ir.semantic import MODEL, QUERY_PREFIX


class QueryHandler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass  # Keep query text out of local logs.

    def reply(self, code, value):
        data = json.dumps(value).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        if self.path not in ("/api/tags", "/api/version"):
            return self.reply(404, {})
        try:
            result = self.server.ollama.get(self.path).raise_for_status().json()
            if self.path == "/api/tags":
                result = {"models": [m for m in result["models"] if m["name"] == MODEL]}
            self.reply(200, result)
        except (httpx.HTTPError, ValueError, KeyError):
            self.reply(503, {"error": "Ollama indisponibile"})

    def do_POST(self):
        if self.path != "/api/embed":
            return self.reply(404, {})
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 8192:
                return self.reply(413, {})
            body = json.loads(self.rfile.read(length))
            values = body["input"]
            if isinstance(values, str):
                values = [values]
            if (body["model"] != MODEL or not isinstance(values, list) or len(values) != 1
                    or not isinstance(values[0], str) or not values[0].startswith(QUERY_PREFIX)
                    or not 0 < len(values[0][len(QUERY_PREFIX):].strip()) <= 250):
                return self.reply(422, {})
        except (KeyError, ValueError, TypeError):
            return self.reply(422, {})
        if not self.server.capacity.acquire(blocking=False):
            return self.reply(503, {"error": "Ollama occupato"})
        try:
            result = self.server.ollama.post("/api/embed", json={
                "model": MODEL, "input": values, "truncate": False, "options": {"num_ctx": 2048}})
            self.reply(200, result.raise_for_status().json())
        except (httpx.HTTPError, ValueError):
            self.reply(503, {"error": "Ollama indisponibile"})
        finally:
            self.server.capacity.release()


def run(host, key):
    log = Path(__file__).resolve().parents[1] / "output" / "ollama-query"
    log.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(filename=log / "tunnel.log", level=logging.INFO,
                        format="%(asctime)s %(message)s")
    with FileLock(str(log / "tunnel.lock"), timeout=0), ThreadingHTTPServer(
        ("127.0.0.1", 11439), QueryHandler
    ) as relay, httpx.Client(base_url="http://127.0.0.1:11434", timeout=115, trust_env=False) as model:
        relay.ollama = model
        relay.capacity = threading.BoundedSemaphore(2)
        threading.Thread(target=relay.serve_forever, daemon=True).start()
        cmd = ["ssh.exe", "-T", "-o", "BatchMode=yes", "-o", "IdentitiesOnly=yes",
               "-o", "StrictHostKeyChecking=yes", "-o", "ExitOnForwardFailure=yes",
               "-o", "ServerAliveInterval=15", "-o", "ServerAliveCountMax=3",
               "-o", "ConnectTimeout=10", "-i", str(key), "-R", "127.0.0.1:21439:127.0.0.1:11439",
               "newsfinder-query@" + host]
        while True:
            # The forced command reads stdin. Closing the parent's pipe ends SSH as well.
            with subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL,
                                  stderr=subprocess.PIPE, text=True,
                                  creationflags=subprocess.CREATE_NO_WINDOW) as ssh:
                logging.info("Connessione SSH avviata")
                ssh.wait()
                logging.warning("SSH terminato (%s): %s", ssh.returncode, ssh.stderr.read()[:500])
            time.sleep(5)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", required=True)
    parser.add_argument("--key", type=Path, required=True)
    args = parser.parse_args()
    run(args.host, args.key)

