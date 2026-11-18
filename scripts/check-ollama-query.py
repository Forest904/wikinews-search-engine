"""Smoke test from inside the production app container."""
import math
import time

import httpx

started = time.monotonic()
with httpx.Client(base_url="http://ollama", timeout=120,
                  transport=httpx.HTTPTransport(uds="/imports/ollama-query/ollama.sock")) as http:
    version = http.get("/api/version").raise_for_status().json()["version"]
    model = "qwen3-embedding:0.6b"
    models = http.get("/api/tags").raise_for_status().json()["models"]
    digest = next(row["digest"] for row in models if row["name"] == model)
    result = http.post("/api/embed", json={"model": model, "input": ["Instruct: Retrieve relevant Italian Wikinews articles for this search query.\nQuery: terremoto in Abruzzo"]})
    vector, = result.raise_for_status().json()["embeddings"]
    if len(vector) != 1024 or not math.isclose(math.hypot(*vector), 1, abs_tol=1e-4):
        raise ValueError("Embedding inatteso")
    print(f"Ollama {version}, {model} {digest[:12]}, {len(vector)} dimensioni, {time.monotonic()-started:.2f} s")

