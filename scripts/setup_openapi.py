#!/usr/bin/env python3
# setup_openapi.py
# Faz: (1) garantir deps, (2) baixar OpenAPI da brapi, (3) gerar modelos Pydantic, (4) opcional: gerar cliente.
# Uso:
#   python scripts/setup_openapi.py
#   python scripts/setup_openapi.py --url https://brapi.dev/swagger/latest.json --generate-client --verbose

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

DEFAULT_URL = "https://brapi.dev/swagger/latest.json"
ROOT = Path(__file__).resolve().parents[1] if (Path(__file__).name == "setup_openapi.py") else Path.cwd()
DEFAULT_SCHEMA = ROOT / "app" / "openapi_schemas" / "latest.json"
DEFAULT_OUT = ROOT / "app" / "openapi_models"
DEFAULT_CLIENT_OUT = ROOT / "clients" / "brapi_openapi"

def log(msg: str, *, verbose: bool = True):
    if verbose:
        print(msg, flush=True)

def run(cmd: list[str], *, check=True, verbose=True):
    log(f"$ {' '.join(cmd)}", verbose=verbose)
    return subprocess.run(cmd, check=check)

def ensure_pkg(module_name: str, pip_name: str | None = None, *, no_install: bool, verbose: bool) -> bool:
    pip_name = pip_name or module_name
    try:
        __import__(module_name)
        log(f"OK {module_name} importado", verbose=verbose)
        return True
    except Exception:
        if no_install:
            log(f"FALTA {module_name} (e --no-install ligado)", verbose=verbose)
            return False
        log(f"Instalando {pip_name} via pip ...", verbose=verbose)
        code = subprocess.call([sys.executable, "-m", "pip", "install", pip_name])
        if code != 0:
            log(f"Falha ao instalar {pip_name}", verbose=verbose)
            return False
        try:
            __import__(module_name)
            log(f"OK {module_name} instalado", verbose=verbose)
            return True
        except Exception:
            log(f"{module_name} ainda indisponivel apos install", verbose=verbose)
            return False

def download_openapi(url: str, dest: Path, *, verbose: bool):
    dest.parent.mkdir(parents=True, exist_ok=True)
    log(f"Baixando OpenAPI de {url}", verbose=verbose)
    with urllib.request.urlopen(url) as resp:
        data = resp.read().decode("utf-8")
    json.loads(data)  # valida basico
    dest.write_text(data, encoding="utf-8")
    log(f"Schema salvo em {dest}", verbose=verbose)

def generate_models(schema_path: Path, out_path: Path, *, verbose: bool) -> int:
    # Se out_path aponta para um diretório (ou não tem sufixo), force arquivo dentro dele
    if out_path.exists() and out_path.is_dir():
        out_file = out_path / "models.py"
    elif out_path.suffix == "":
        out_file = out_path / "models.py"
    else:
        out_file = out_path

    out_file.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable, "-m", "datamodel_code_generator",
        "--input", str(schema_path),
        "--input-file-type", "openapi",
        "--output", str(out_file),
        "--target-python-version", "3.11",
        "--use-standard-collections",
        "--use-double-quotes",
        "--collapse-root-models",
        "--snake-case-field",
        "--enum-field-as-literal", "all",
        "--disable-timestamp",
        "--reuse-model",
        "--base-class", "pydantic.BaseModel",
    ]
    return run(cmd, check=False, verbose=verbose).returncode


def generate_client(schema_path: Path, out_dir: Path, *, verbose: bool) -> int:
    out_dir.parent.mkdir(parents=True, exist_ok=True)
    if out_dir.exists():
        shutil.rmtree(out_dir)
    cmd = [
        sys.executable, "-m", "openapi_python_client", "generate",
        "--path", str(schema_path),
        "--output", str(out_dir),
        "--overwrite",
    ]
    return run(cmd, check=False, verbose=verbose).returncode

def main():
    parser = argparse.ArgumentParser(description="Pipeline OpenAPI brapi: fetch + gerar modelos (+ cliente opcional).")
    parser.add_argument("--url", default=os.environ.get("BRAPI_OPENAPI_URL", DEFAULT_URL))
    parser.add_argument("--schema", default=str(DEFAULT_SCHEMA))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--generate-client", action="store_true", default=False)
    parser.add_argument("--client-out", default=str(DEFAULT_CLIENT_OUT))
    parser.add_argument("--no-install", action="store_true", default=False)
    parser.add_argument("--verbose", action="store_true", default=False)
    args = parser.parse_args()

    verbose = args.verbose
    schema_path = Path(args.schema)
    out_dir = Path(args.out)
    client_out = Path(args.client_out)

    ok_codegen = ensure_pkg("datamodel_code_generator", "datamodel-code-generator", no_install=args.no_install, verbose=verbose)
    ok_client = ensure_pkg("openapi_python_client", "openapi-python-client", no_install=args.no_install, verbose=verbose)

    if not ok_codegen:
        print("Erro: datamodel_code_generator nao disponivel. Instale ou rode sem --no-install.", file=sys.stderr)
        sys.exit(2)

    if not schema_path.exists():
        try:
            download_openapi(args.url, schema_path, verbose=verbose)
        except Exception as e:
            print(f"Falha ao baixar schema: {e}", file=sys.stderr)
            sys.exit(3)
    else:
        log(f"Schema ja existe em {schema_path} (apague para forcar novo download).", verbose=verbose)

    rc = generate_models(schema_path, out_dir, verbose=verbose)
    if rc != 0:
        print(f"Falha ao gerar modelos (exit={rc}).", file=sys.stderr)
        sys.exit(4)
    log(f"Modelos gerados em {out_dir}", verbose=verbose)

    if args.generate_client:
        if not ok_client:
            print("Aviso: openapi-python-client nao disponivel; pulando geracao de cliente.", file=sys.stderr)
        else:
            rc2 = generate_client(schema_path, client_out, verbose=verbose)
            if rc2 != 0:
                print(f"Aviso: falha ao gerar cliente (exit={rc2}).", file=sys.stderr)
            else:
                log(f"Cliente gerado em {client_out}", verbose=verbose)

    log("Concluido.", verbose=True)

if __name__ == "__main__":
    main()
