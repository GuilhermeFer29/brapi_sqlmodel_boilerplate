import hashlib
import json


def make_cache_key(prefix: str, *parts: str | dict) -> str:
    norm = []
    for p in parts:
        if isinstance(p, dict):
            norm.append(json.dumps(p, sort_keys=True, separators=(",", ":")))
        else:
            norm.append(str(p))
    digest_source = "::".join(norm)
    digest = hashlib.sha256(digest_source.encode()).hexdigest()[:16]
    human_part = "::".join(norm[:3])  # mantém porção legível para limpeza
    return f"{prefix}:{human_part}:{digest}"
