"""Utilitários para serialização JSON com suporte a datetime."""
from datetime import datetime
from typing import Any
import json


def json_serializer(obj):
    """
    Serializa objetos datetime para formato ISO 8601.
    
    Usado como parâmetro `default` em json.dumps() para lidar com
    objetos que não são nativamente serializáveis em JSON.
    
    Args:
        obj: Objeto a ser serializado
        
    Returns:
        String ISO 8601 se for datetime
        
    Raises:
        TypeError: Se o objeto não for serializável
    """
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


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
