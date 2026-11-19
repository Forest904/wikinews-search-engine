"""Benchmark-only ASGI entrypoint serving frozen MediaWiki API responses."""

import json
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path

import httpx

from wikinews_ir.adapters.live import LiveSearch
from wikinews_ir.api.main import create_app, lifespan


class Replay:
    def __init__(self):
        path = Path(os.environ["REPLAY_FILE"])
        self.pages = json.loads(path.read_text("utf-8"))
        self.delay = float(os.getenv("REPLAY_DELAY_MS", "0")) / 1000

    def query(self, params, *, deadline=None):
        remaining = deadline - time.monotonic()
        time.sleep(max(0, min(remaining, self.delay)))
        if remaining <= self.delay:
            raise httpx.ReadTimeout("Replay deadline")
        if "responses" in self.pages:
            return self.pages["responses"][json.dumps(params, sort_keys=True)]
        if params.get("list") == "search":
            return self.pages["search"][params["srsearch"]][str(params.get("sroffset", 0))]
        return self.pages[params["prop"]]


app = create_app()


@asynccontextmanager
async def replay_lifespan(app):
    async with lifespan(app):
        app.state.wikinews = LiveSearch(Replay())
        yield


app.router.lifespan_context = replay_lifespan
