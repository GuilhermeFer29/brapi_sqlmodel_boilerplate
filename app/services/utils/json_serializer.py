"""Utilitários para serialização JSON com suporte a datetime."""
from datetime import datetime, timezone
from typing import Any, Optional
import json


def json_serializer(obj):
    """
    Serializa objetos datetime para formato ISO 8601.
    
    Usado como parâmetro `default` em json.dumps() para lidar com
    objetos que não são nativamente serializáveis em JSON.
    
    Args:
    - obj: Objeto a ser serializado
    
    Returns:
    - String ISO 8601 se for datetime
    
    Raises:
    - TypeError: Se o objeto não for serializável
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


# ---------------------------------------------------------------------------
# Normalization helpers used across services (Stage 3)
# ---------------------------------------------------------------------------

def normalize_numeric(value: Any) -> Any:
    """Converte valores numéricos que chegam como string para ``int``/``float``.

    - ``None`` ou strings vazias retornam ``None``.
    - Se a conversão falhar, ``None`` é retornado para evitar "false zeros".
    """
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return None
        try:
            # Prefer int when possible
            if stripped.isdigit():
                return int(stripped)
            return float(stripped.replace(",", "."))
        except ValueError:
            return None
    return None

def normalize_timestamp(ts: Any) -> Optional[str]:
    """Normaliza timestamps para ISO‑8601 strings.

    Aceita ``datetime`` (já com tzinfo ou assume UTC), timestamps em segundos
    (int/float) ou strings ISO. Retorna ``None`` quando não for possível
    interpretar.
    """
    if ts is None:
        return None
    if isinstance(ts, datetime):
        return ts.isoformat() if ts.tzinfo else ts.replace(tzinfo=timezone.utc).isoformat()
    # epoch seconds
    if isinstance(ts, (int, float)):
        try:
            return datetime.fromtimestamp(int(ts), tz=timezone.utc).isoformat()
        except Exception:
            return None
    if isinstance(ts, str):
        cleaned = ts.strip()
        if not cleaned:
            return None
        # handle trailing Z
        if cleaned.endswith("Z"):
            cleaned = cleaned[:-1] + "+00:00"
        try:
            return datetime.fromisoformat(cleaned).isoformat()
        except Exception:
            return None
    return None


def normalize_for_json(data: Any) -> Any:
    """
    Normaliza dados para serem serializáveis em JSON, convertendo datetime para ISO 8601.
    
    Útil para preparar dados antes de salvar em colunas JSON do banco de dados.
    
    Args:
        data: Dados a serem normalizados (dict, list, ou valor primitivo)
        
    Returns:
        Dados normalizados com datetime convertidos para strings ISO 8601
    """
    if data is None:
        return None
    # Serializa e deserializa para converter datetime recursivamente
    return json.loads(json.dumps(data, default=json_serializer))
