"""Environment-based settings for local development."""

import math
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
    elasticsearch_italian_index: str = "wikinews_italian_v1"
    elasticsearch_timeout: float = 5.0

    def __post_init__(self):
        if not math.isfinite(self.elasticsearch_timeout) or self.elasticsearch_timeout <= 0:
            raise ValueError("ELASTICSEARCH_TIMEOUT must be a finite positive number")


@lru_cache
def get_settings() -> Settings:
    return Settings(
        elasticsearch_url=os.getenv("ELASTICSEARCH_URL", "http://127.0.0.1:9200"),
        elastic_password=os.getenv("ELASTIC_PASSWORD", ""),
        elasticsearch_index=os.getenv("ELASTICSEARCH_INDEX", "wikinews_standard_v1"),
        elasticsearch_italian_index=os.getenv("ELASTICSEARCH_ITALIAN_INDEX", "wikinews_italian_v1"),
        elasticsearch_timeout=float(os.getenv("ELASTICSEARCH_TIMEOUT", "5")),
    )
