from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.services.macro_service import get_inflation, get_prime_rate

router = APIRouter(prefix="/api", tags=["macro"])

@router.get("/inflation")
async def inflation(
    country: str = Query("brazil", description="País: brazil, united_states"),
    session: AsyncSession = Depends(get_session)
):
    """
    Retorna histórico de inflação de um país.
    
    **Retorna:**
    - Série histórica de inflação
    - Data de referência de cada ponto
    - Valor percentual da inflação
    
    **Exemplo de resposta:**
    ```json
    {
      "cached": false,
      "results": {
        "data": [{
          "date": "2025-09-01",
          "value": 4.82,
          "country": "brazil"
        }, {
          "date": "2025-08-01",
          "value": 4.24,
          "country": "brazil"
        }]
      }
    }
    ```
    
    **Uso:** Análise macroeconômica e ajuste de investimentos pela inflação.
    """
    return await get_inflation(session, country)

@router.get("/prime-rate")
async def prime_rate(
    country: str = Query("brazil", description="País: brazil, united_states"),
    session: AsyncSession = Depends(get_session)
):
    """
    Retorna histórico da taxa básica de juros (Selic no Brasil, Fed Rate nos EUA).
    
    **Retorna:**
    - Série histórica da taxa de juros
    - Data de referência de cada ponto
    - Valor percentual da taxa
    
    **Exemplo de resposta:**
    ```json
    {
      "cached": false,
      "results": {
        "data": [{
          "date": "2025-09-01",
          "value": 10.75,
          "country": "brazil"
        }, {
          "date": "2025-08-01",
          "value": 10.50,
          "country": "brazil"
        }]
      }
    }
    ```
    
    **Uso:** Análise de política monetária e decisões de investimento em renda fixa.
    """
    return await get_prime_rate(session, country)
