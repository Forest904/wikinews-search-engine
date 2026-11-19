"""Freeze expected search pages from a known-good replica for k6 ORACLE checks."""

import argparse
import json
from pathlib import Path

import httpx

if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("url")
    p.add_argument("output", type=Path)
    p.add_argument("--queries", nargs="+", default=["Italia", "Roma", "elezioni", "terremoto"])
    p.add_argument("--profiles", nargs="+", default=["E1"])
    args = p.parse_args()
    expected = {}
    with httpx.Client(base_url=args.url, timeout=30) as client:
        for q in args.queries:
            for profile in args.profiles:
                for page, filtered in ((1, False), (1, True), (2, True)):
                    params = dict(q=q, profile=profile, page=page)
                    if filtered:
                        params.update(year_from=2005, year_to=2021)
                    r = client.get("/api/search", params=params)
                    r.raise_for_status()
                    key = json.dumps(
                        [q, profile, page, filtered], separators=(",", ":"), ensure_ascii=False
                    )
                    expected[key] = [h["document_id"] for h in r.json()["hits"]]
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(expected, f, ensure_ascii=False, indent=2)
