#!/usr/bin/env python3
import os, pathlib, json, httpx
DEST = pathlib.Path(__file__).resolve().parents[1] / "app" / "openapi_schemas" / "latest.json"
URL = os.environ.get("BRAPI_OPENAPI_URL", "https://brapi.dev/swagger/latest.json")
with httpx.Client(timeout=30.0) as client:
    r = client.get(URL); r.raise_for_status(); DEST.parent.mkdir(parents=True, exist_ok=True); DEST.write_text(r.text, encoding="utf-8")
json.loads(DEST.read_text("utf-8"))
print("OpenAPI salvo em", DEST)
