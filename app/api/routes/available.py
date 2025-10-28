from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.services.available_service import get_available

router = APIRouter(prefix="/api", tags=["available"])

@router.get("/available")
async def available(session: AsyncSession = Depends(get_session)):
    """
    Retorna lista de todos os ativos disponíveis na B3 (ações, FIIs, ETFs, BDRs).
    
    **Retorna:**
    - Lista completa de tickers disponíveis
    - Nome curto de cada ativo
    - Tipo do ativo (stock, fund, ETF, BDR)
    
    **Exemplo de resposta:**
    ```json
    {
      "cached": false,
      "results": {
        "stocks": ["PETR4", "VALE3", "ITUB4", "BBDC4"],
        "indexes": ["IBOV", "IFIX", "SMLL"],
        "availableSectors": ["Financeiro", "Petróleo", "Mineração"],
        "availableStockTypes": ["stock", "fund", "ETF", "BDR"]
      }
    }
    ```
    
    **Uso:** Ideal para popular dropdowns e autocomplete de tickers.
    """
    return await get_available(session)
