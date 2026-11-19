"""Record two pages of public API responses per query for an offline replay."""

import argparse
import asyncio
import json
import time
from pathlib import Path

from wikinews_ir.adapters.live import LiveSearch
from wikinews_ir.adapters.mediawiki import MediaWiki


class Recorder(MediaWiki):
    def __init__(self):
        super().__init__()
        self.responses = {}

    def query(self, params, **kwargs):
        result = super().query(params, **kwargs)
        self.responses[json.dumps(params, sort_keys=True)] = result
        return result


async def record(queries):
    api = Recorder()
    try:
        source = LiveSearch(api)
        for query in queries:
            page = await source.page(query, "", time.monotonic() + 10)
            if page["next_cursor"]:
                await source.page(query, page["next_cursor"], time.monotonic() + 10)
        return dict(recorded_epoch=time.time(), queries=queries, responses=api.responses)
    finally:
        api.close()


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("output", type=Path)
    p.add_argument("queries", nargs="+")
    args = p.parse_args()
    capture = asyncio.run(record(args.queries))
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(capture, f, ensure_ascii=False)
