"""Versioned configurations, also included in the wheel and container."""

import hashlib
import json
import math
from pathlib import Path
from typing import Literal, get_args

import yaml

CONFIGS = Path(__file__).resolve().parents[1] / "resources"
ProfileId = Literal["E0", "E1", "E2", "E3", "E4"]
SUPPORTED_PROFILES = get_args(ProfileId)


def digest(value):
    raw = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def profile_config(profile):
    if profile not in SUPPORTED_PROFILES:
        raise ValueError(f"Retrieval profile not implemented: {profile}")
    config = yaml.safe_load((CONFIGS / "retrieval" / f"{profile}.yaml").read_text("utf-8"))
    if not isinstance(config, dict):
        raise ValueError(f"Configurazione profilo non valida: {profile}")
    expected = {
        "id": profile, "version": "1", "index_family":
        "standard" if profile == "E0" else "italian",
        "query_type": "multi_match", "type": "best_fields", "operator": "or",
        "fields": ["title", "body"],
    }
    if profile in {"E2", "E3", "E4"}:
        version = config.get("version")
        if not isinstance(version, str) or not version.isascii() or not version.isdigit() or int(version) < 1:
            raise ValueError("Versione profilo non valida")
        expected["version"] = version
        expected["fields"] = ["title", "body"]
        parameters = {"title_boost": 3.0}
        if profile == "E3":
            parameters.update(fuzzy_boost=0.2, fuzziness="AUTO:4,7", prefix_length=1,
                              max_expansions=25, fuzzy_transpositions=True)
        if profile == "E4":
            parameters.update(phrase_boost=2.0, slop=0, quote_syntax_version="1")
        for key, default in parameters.items():
            value = config.get(key)
            if isinstance(default, float):
                if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
                    raise ValueError(f"Parametro non valido: {key}")
            elif type(value) is not type(default) or value != default:
                raise ValueError(f"Parametro non valido: {key}")
            expected[key] = value
    if config != expected:
        raise ValueError(f"Configurazione profilo incompatibile: {profile}")
    return config


def index_config(profile):
    family = profile_config(profile)["index_family"]
    return json.loads((CONFIGS / "indices" / f"{family}.json").read_text("utf-8"))


def index_name(settings, profile):
    profile_config(profile)
    return settings.elasticsearch_index if profile == "E0" else settings.elasticsearch_italian_index
