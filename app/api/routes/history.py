from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session
from app.services.history_service import get_history

router = APIRouter(prefix="/api/quote", tags=["quote-history"])


@router.get("/history")
async def quote_history(
    ticker: str = Query(..., description="Ticker do ativo, ex: HGLG11, PETR4, VALE3"),
    period: str = Query("3mo", description="Período: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max"),
    interval: str = Query("1d", description="Intervalo: 1m, 5m, 15m, 1h, 1d, 1wk, 1mo"),
    session: AsyncSession = Depends(get_session),
):
    """
    Retorna histórico OHLCV simplificado e normalizado de um ativo.
    
    **Retorna:**
    - Dados OHLCV (Open, High, Low, Close, Volume)
    - Datas em formato ISO 8601
    - Apenas os dados essenciais (sem campos extras)
    
    **Exemplo de resposta:**
    ```json
    {
      "cached": false,
      "symbol": "HGLG11",
      "items": [
        {
          "date": "2025-07-25T13:00:00+00:00",
          "open": 154.89,
          "high": 156.62,
          "low": 153.81,
          "close": 155.71,
          "volume": 36429
        },
        {
          "date": "2025-07-28T13:00:00+00:00",
          "open": 156.30,
          "high": 156.30,
          "low": 153.99,
          "close": 154.70,
          "volume": 45039
        }
      ]
    }
    ```
    
    **Uso:** Ideal para gráficos de candlestick e análise técnica.
    
    **Diferença do /api/quote:**
    - Mais leve (apenas OHLCV)
    - Datas em ISO 8601 (não timestamp)
    - Sem dados fundamentalistas
    """
    try:
        data = await get_history(session, ticker, period, interval)
        return data
    except HTTPException:
        raise
    except Exception as e:
        # erro inesperado do nosso lado → 500
        raise HTTPException(status_code=500, detail=str(e))
