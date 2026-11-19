"""Interactive Wikinotizie search, with optional current-page thumbnails."""

import asyncio
import base64
import json
import logging
import time
from collections import OrderedDict
from threading import Lock
from urllib.parse import quote

import httpx
from bs4 import BeautifulSoup

from .images import fetch_images

log = logging.getLogger(__name__)


def continuation(cursor):
    if not cursor:
        return {}
    try:
        data = json.loads(base64.urlsafe_b64decode(cursor))
        if (
            isinstance(data, dict)
            and set(data) == {"continue", "sroffset"}
            and type(data["sroffset"]) is int
            and data["sroffset"] > 0
            and isinstance(data["continue"], str)
        ):
            return data
    except (ValueError, TypeError):
        pass
    raise ValueError("Cursore non valido")


class LiveSearch:
    def __init__(self, api):
        self.api = api
        self.cache = OrderedDict()
        self.lock = Lock()

    async def page(self, query, cursor, deadline):
        key = (query, cursor)
        with self.lock:
            entry = self.cache.get(key)
            if entry and entry[0] > time.monotonic():
                self.cache.move_to_end(key)
                return entry[1]
        params = dict(
            action="query",
            format="json",
            formatversion=2,
            list="search",
            srnamespace=0,
            srsearch=query,
            srprop="snippet",
            srlimit=10,
            **continuation(cursor),
        )
        data = await asyncio.wait_for(
            asyncio.to_thread(self.api.query, params, deadline=deadline),
            max(0, deadline - time.monotonic()),
        )
        hits = [
            {
                "document_id": str(hit["pageid"]),
                "pageid": hit["pageid"],
                "title": hit["title"],
                "snippet": BeautifulSoup(hit.get("snippet", ""), "html.parser").get_text(),
                "url": "https://it.wikinews.org/wiki/"
                + quote(hit["title"].replace(" ", "_"), safe=""),
                "image": None,
            }
            for hit in data["query"]["search"]
        ]
        if hits:
            try:
                images = await asyncio.wait_for(
                    asyncio.to_thread(self.page_images, hits, deadline),
                    max(0, deadline - time.monotonic()),
                )
                for hit in hits:
                    hit["image"] = images.get(hit["pageid"])
            except (TimeoutError, httpx.HTTPError, ValueError, KeyError):
                log.info("Miniature Wikimedia temporaneamente indisponibili")
        token = data.get("continue")
        page = dict(
            hits=hits,
            total=data["query"].get("searchinfo", {}).get("totalhits", len(hits)),
            next_cursor=base64.urlsafe_b64encode(json.dumps(token).encode()).decode()
            if token
            else None,
        )
        with self.lock:
            self.cache[key] = (time.monotonic() + 120, page)
            self.cache.move_to_end(key)
            if len(self.cache) > 256:
                self.cache.popitem(last=False)
        return page

    def page_images(self, hits, deadline):
        pages = self.api.query(
            dict(
                action="query",
                format="json",
                formatversion=2,
                prop="pageimages",
                piprop="name",
                pilimit=10,
                pageids="|".join(h["document_id"] for h in hits),
            ),
            deadline=deadline,
        )["query"]["pages"]
        names = {p["pageid"]: p["pageimage"] for p in pages if p.get("pageimage")}
        if names:
            images = fetch_images(self.api, list(dict.fromkeys(names.values())), 128, deadline)
            return {pid: images.get(name) for pid, name in names.items()}
        return {}
