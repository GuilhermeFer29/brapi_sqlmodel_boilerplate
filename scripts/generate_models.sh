#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/app/openapi_schemas/latest.json"
OUT="$ROOT/app/openapi_models"
if [[ ! -f "$SRC" ]]; then echo "Schema não encontrado: $SRC"; exit 1; fi
rm -rf "$OUT"; mkdir -p "$OUT"
datamodel-code-generator --input "$SRC" --input-file-type openapi --output "$OUT" --target-python-version 3.11 --use-standard-collections --use-double-quotes --collapse-root-models --snake-case-field --enum-field-as-literal all --disable-timestamp --reuse-model --base-class pydantic.BaseModel
echo "Modelos gerados em $OUT"
