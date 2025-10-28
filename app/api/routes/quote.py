from fastapi import APIRouter, Depends, Query
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.services.quote_service import get_quote

router = APIRouter(prefix="/api", tags=["quote"])

@router.get("/quote")
async def quote(
    tickers: str = Query(..., description="Lista separada por vírgula, ex: PETR4,VALE3"),
    range: Optional[str] = Query(None, description="Período histórico: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, max"),
    interval: Optional[str] = Query(None, description="Intervalo dos dados: 1m, 5m, 15m, 1h, 1d, 1wk, 1mo"),
    modules: Optional[str] = Query(None, description="Módulos adicionais separados por vírgula"),
    session: AsyncSession = Depends(get_session),
):
    """
    Retorna cotações completas de ações/FIIs com dados de mercado e histórico opcional.
    
    **Retorna:**
    - Preços atuais (abertura, fechamento, máxima, mínima)
    - Volume negociado
    - Variação percentual
    - Histórico de preços (se `range` e `interval` forem especificados)
    - Dados fundamentalistas (se `modules` for especificado)
    
    **Exemplo de resposta:**
    ```json
    {
      "cached": false,
      "results": [{
        "symbol": "PETR4",
        "shortName": "PETROBRAS PN",
        "regularMarketPrice": 38.50,
        "regularMarketChange": 0.85,
        "regularMarketChangePercent": 2.26,
        "regularMarketVolume": 45000000,
        "historicalDataPrice": [
          {"date": 1729699200, "open": 37.80, "high": 38.90, "low": 37.50, "close": 38.50, "volume": 45000000}
        ]
      }]
    }
    ```
    """
    params = {}
    if range: params["range"] = range
    if interval: params["interval"] = interval
    if modules: params["modules"] = modules
    return await get_quote(session, tickers, params)
