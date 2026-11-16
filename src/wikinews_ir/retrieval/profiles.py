"""Versioned configurations, also included in the wheel and container."""

import hashlib
import json
from pathlib import Path

import yaml

CONFIGS = Path(__file__).resolve().parents[1] / "resources"
SUPPORTED_PROFILES = ("E0", "E1")


def digest(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def profile_config(profile):
    if profile not in SUPPORTED_PROFILES:
        raise ValueError(f"Retrieval profile not implemented: {profile}")
    config = yaml.safe_load((CONFIGS / "retrieval" / f"{profile}.yaml").read_text("utf-8"))
    expected = {
        "id": profile, "version": "1", "index_family":
        "standard" if profile == "E0" else "italian",
        "query_type": "multi_match", "type": "best_fields", "operator": "or",
        "fields": ["title", "body"],
    }
    if config != expected:
        raise ValueError(f"Configurazione baseline incompatibile: {profile}")
    return config


def index_config(profile):
    family = profile_config(profile)["index_family"]
    return json.loads((CONFIGS / "indices" / f"{family}.json").read_text("utf-8"))


def index_name(settings, profile):
    profile_config(profile)
    return settings.elasticsearch_index if profile == "E0" else settings.elasticsearch_italian_index
