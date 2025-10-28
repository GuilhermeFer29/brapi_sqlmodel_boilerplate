from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.services.currency_service import get_currency

router = APIRouter(prefix="/api", tags=["currency"])

@router.get("/currency")
async def currency(
    currency: str = Query(..., description="Pares de moedas separados por vírgula, ex: USD-BRL,EUR-BRL,GBP-BRL"),
    session: AsyncSession = Depends(get_session),
):
    """
    Retorna cotações de pares de moedas (câmbio) em tempo real.
    
    **Retorna:**
    - Taxa de compra (bid)
    - Taxa de venda (ask)
    - Variação percentual
    - Timestamp da última atualização
    
    **Exemplo de resposta:**
    ```json
    {
      "cached": false,
      "results": {
        "currency": [{
          "fromCurrency": "USD",
          "toCurrency": "BRL",
          "name": "Dólar Americano/Real Brasileiro",
          "bid": 5.02,
          "ask": 5.03,
          "high": 5.05,
          "low": 5.00,
          "pctChange": 0.45,
          "regularMarketTime": "2025-10-23T20:00:00+00:00"
        }]
      }
    }
    ```
    
    **Uso:** Conversão de moedas e monitoramento de câmbio.
    """
    return await get_currency(session, currency)
