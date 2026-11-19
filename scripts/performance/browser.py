"""Measure visible search and reader transitions in a real Chromium session."""

import argparse
import json
import time
from pathlib import Path
from urllib.parse import unquote, urlsplit

from playwright.sync_api import expect, sync_playwright


def probe(page, url, query, profile):
    nav = page.goto(url)
    if nav is None or not nav.ok:
        raise ValueError("Home unavailable")
    page.locator("#filters").click()
    page.locator("#profile").select_option(profile)
    page.locator("#q").fill(query)
    start = time.perf_counter()
    page.locator("#q").press("Enter")
    link = page.locator("#results .result-copy a").first
    expect(link).to_be_visible()
    first_ms = (time.perf_counter() - start) * 1000
    expected = unquote(urlsplit(link.get_attribute("href")).path.split("/")[-1])
    start = time.perf_counter()
    link.click()
    body = page.locator(".article-body")
    expect(body).to_be_visible()
    reader_ms = (time.perf_counter() - start) * 1000
    expect(page.locator(".save-button")).to_have_attribute("data-id", expected)
    if not body.inner_text().strip():
        raise ValueError("Empty article")
    timing = page.evaluate("performance.getEntriesByType('navigation')[0].toJSON()")
    return dict(
        first_result_ms=first_ms,
        reader_ms=reader_ms,
        article=expected,
        reader_ttfb_ms=timing["responseStart"] - timing["requestStart"],
        home_cache=nav.headers.get("cf-cache-status"),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("url")
    parser.add_argument("output", type=Path)
    parser.add_argument("--query", default="Roma")
    parser.add_argument("--profile", default="E1")
    parser.add_argument("--location", required=True)
    parser.add_argument("--repeats", type=int, default=3)
    args = parser.parse_args()
    errors = 0
    with sync_playwright() as pw, args.output.open("x", encoding="utf-8") as stream:
        browser = pw.chromium.launch()
        for i in range(args.repeats):
            page = browser.new_page()
            row = dict(
                iteration=i,
                location=args.location,
                url=args.url,
                query=args.query,
                profile=args.profile,
                epoch=time.time(),
                chromium=browser.version,
            )
            try:
                row.update(probe(page, args.url, args.query, args.profile))
            except Exception as exc:
                row["error"] = str(exc)
                errors += 1
            finally:
                page.close()
            stream.write(json.dumps(row) + "\n")
        browser.close()
    raise SystemExit(int(errors > 0))
