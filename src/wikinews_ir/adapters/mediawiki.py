"""Shared transport for public MediaWiki Action API reads."""

import logging
import os
import time
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime

import httpx

ENDPOINT = "https://it.wikinews.org/w/api.php"
DEFAULT_AGENT = "NewsFinder/1.0 (https://github.com/Forest904/wikinews-search-engine/issues)"
log = logging.getLogger(__name__)


def retry_delay(response, fallback):
    value = response.headers.get("Retry-After", "") if response is not None else ""
    if value.isdigit():
        return int(value)
    try:
        return max(0, parsedate_to_datetime(value).timestamp() - time.time())
    except (TypeError, ValueError, OverflowError):
        return fallback


class MediaWiki:
    def __init__(self, user_agent=None, client=None, sleep=time.sleep):
        self.agent = user_agent or os.getenv("WIKIMEDIA_USER_AGENT") or DEFAULT_AGENT
        if not self.agent.strip():
            raise ValueError("User-Agent identificabile con contatto richiesto")
        self.http = client if client is not None else httpx.Client(timeout=30)
        self.owned = client is None
        self.sleep = sleep

    def close(self):
        if self.owned:
            self.http.close()

    def query(self, params, *, deadline=None, audit=None):
        for attempt in range(3):
            timeout = 30 if deadline is None else deadline - time.monotonic()
            if timeout <= 0:
                raise httpx.TimeoutException("Tempo Wikimedia esaurito")
            response = None
            started = time.monotonic()
            entry = {"at": datetime.now(UTC).isoformat(), "params": params}
            try:
                response = self.http.get(
                    ENDPOINT, params=params, timeout=timeout, headers={"User-Agent": self.agent}
                )
            except httpx.TransportError as exc:
                if audit:
                    audit({**entry, "error": str(exc)})
                failure = exc
            else:
                log.info(
                    "Wikimedia module=%s status=%d latency_ms=%d",
                    params.get("prop", params.get("list")),
                    response.status_code,
                    (time.monotonic() - started) * 1000,
                )
                if audit:
                    audit(
                        {
                            **entry,
                            "status_code": response.status_code,
                            "response_text": response.text,
                        }
                    )
                if response.status_code == 429 or response.status_code >= 500:
                    failure = httpx.HTTPStatusError(
                        "Wikimedia indisponibile", request=response.request, response=response
                    )
                else:
                    response.raise_for_status()
                    data = response.json()
                    if data.get("error", {}).get("code") in {
                        "maxlag",
                        "ratelimited",
                        "cirrussearch-too-busy-error",
                    }:
                        failure = ValueError(data["error"]["code"])
                    elif "error" in data or "warnings" in data:
                        raise ValueError("MediaWiki error/warning")
                    else:
                        return data
            delay = retry_delay(response, 2**attempt)
            if attempt == 2 or (deadline is not None and time.monotonic() + delay >= deadline):
                raise failure
            self.sleep(delay)
