from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.services.crypto_service import get_crypto

router = APIRouter(prefix="/api", tags=["crypto"])

@router.get("/crypto")
async def crypto(
    coin: str = Query(..., description="Criptomoedas separadas por vírgula, ex: BTC,ETH,USDT"),
    currency: str = Query("USD", description="Moeda de cotação: USD ou BRL"),
    session: AsyncSession = Depends(get_session),
):
    """
    Retorna cotações de criptomoedas em tempo real.
    
    **Retorna:**
    - Preço atual da criptomoeda
    - Variação nas últimas 24h
    - Variação percentual
    - Timestamp da última atualização
    
    **Exemplo de resposta:**
    ```json
    {
      "cached": false,
      "results": {
        "coins": [{
          "coin": "BTC",
          "name": "Bitcoin",
          "currency": "USD",
          "regularMarketPrice": 67850.50,
          "regularMarketChange": 1250.30,
          "regularMarketChangePercent": 1.88,
          "regularMarketTime": "2025-10-23T20:00:00+00:00"
        }]
      }
    }
    ```
    
    **Uso:** Monitoramento de preços de criptomoedas em diferentes moedas.
    """
    return await get_crypto(session, coin, currency)
