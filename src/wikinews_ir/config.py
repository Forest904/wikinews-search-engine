"""Environment-based settings for local development."""

import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    elasticsearch_url: str = "http://127.0.0.1:9200"
    elastic_password: str = ""
    elasticsearch_index: str = "wikinews_standard_v1"
    elasticsearch_timeout: float = 5.0


@lru_cache
def get_settings() -> Settings:
    return Settings(
        elasticsearch_url=os.getenv("ELASTICSEARCH_URL", "http://127.0.0.1:9200"),
        elastic_password=os.getenv("ELASTIC_PASSWORD", ""),
        elasticsearch_index=os.getenv("ELASTICSEARCH_INDEX", "wikinews_standard_v1"),
        elasticsearch_timeout=float(os.getenv("ELASTICSEARCH_TIMEOUT", "5")),
    )
