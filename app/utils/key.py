import hashlib, json
def make_cache_key(prefix: str, *parts: str | dict) -> str:
    norm = []
    for p in parts:
        if isinstance(p, dict):
            norm.append(json.dumps(p, sort_keys=True, separators=(",", ":")))
        else:
            norm.append(str(p))
    joined = "::".join(norm)
    return f"{prefix}:{hashlib.sha256(joined.encode()).hexdigest()[:16]}"
