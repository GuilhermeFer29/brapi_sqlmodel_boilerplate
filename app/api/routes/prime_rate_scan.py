from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.prime_rate_scan_service import scan_prime_rate

router = APIRouter(prefix="/api/macro", tags=["macro-prime-rate"])


@router.get("/prime-rate/scan")
async def prime_rate_scan(
    include_latest: bool = Query(True, description="Se true, busca também o último valor por país"),
    concurrency: int = Query(6, ge=1, le=16, description="Limite de concorrência das chamadas por país (1-16)"),
    session: AsyncSession = Depends(get_session),
):
    """
    Retorna lista de países disponíveis para consulta de taxa básica de juros (prime rate).
    
    **Retorna:**
    - Lista de países disponíveis
    - Último valor da taxa de juros de cada país (se `include_latest=true`)
    - Data da última atualização
    - Status de cache
    
    **Parâmetros:**
    - `include_latest`: Se true, busca o valor mais recente de cada país
    - `concurrency`: Controla quantas requisições paralelas são feitas (1-16)
    
    **Exemplo de resposta (include_latest=true):**
    ```json
    {
      "cached": false,
      "countries": ["brazil", "united_states", "european_union", "united_kingdom"],
      "latest_values": {
        "brazil": {
          "country": "brazil",
          "date": "2025-09-01",
          "value": 10.75,
          "cached": true
        },
        "united_states": {
          "country": "united_states",
          "date": "2025-09-15",
          "value": 5.50,
          "cached": false
        }
      }
    }
    ```
    
    **Exemplo de resposta (include_latest=false):**
    ```json
    {
      "cached": true,
      "countries": ["brazil", "united_states", "european_union", "united_kingdom"]
    }
    ```
    
    **Uso:** Descobrir quais países têm dados disponíveis e obter snapshot rápido das taxas atuais.
    """
    try:
        data = await scan_prime_rate(session, include_latest=include_latest, concurrency=concurrency)
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
