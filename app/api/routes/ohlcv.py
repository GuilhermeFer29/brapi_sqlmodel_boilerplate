from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta
from app.db.session import get_session
from app.services.ohlcv_service import get_ohlcv, backfill_ohlcv, update_ohlcv_latest, get_available_dates
from app.services.catalog_service import get_asset_by_ticker

router = APIRouter(prefix="/api/ohlcv", tags=["ohlcv"])

@router.get("")
async def get_ohlcv_data(
    ticker: str = Query(..., description="Símbolo do ativo (ex: PETR4, VALE3)"),
    period: str = Query("3mo", description="Período: 1mo, 3mo, 6mo, 1y, 2y, max"),
    interval: str = Query("1d", description="Intervalo: 1d, 1wk, 1mo"),
    start_date: Optional[str] = Query(None, description="Data inicial (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Data final (YYYY-MM-DD)"),
    limit: Optional[int] = Query(None, ge=1, le=1000, description="Limite de registros"),
    session: AsyncSession = Depends(get_session),
):
    """
    Retorna dados históricos OHLCV de um ativo.
    
    **Parâmetros:**
    - `ticker`: Símbolo do ativo (obrigatório)
    - `period`: Período desejado (sobrescreve start/end_date)
    - `interval`: Intervalo dos dados
    - `start_date`: Data inicial específica (YYYY-MM-DD)
    - `end_date`: Data final específica (YYYY-MM-DD)
    - `limit`: Limite de registros (1-1000)
    
    **Retorno:**
    ```json
    {
      "ticker": "PETR4",
      "data": [
        {
          "date": "2024-01-15T00:00:00Z",
          "open": 38.20,
          "high": 39.00,
          "low": 37.80,
          "close": 38.50,
          "volume": 45678901,
          "adj_close": 38.50
        }
      ],
      "count": 65
    }
    ```
    """
    try:
        # Validar que o ativo existe no catálogo
        asset = await get_asset_by_ticker(session, ticker)
        if not asset:
            raise HTTPException(status_code=404, detail=f"Ativo {ticker} não encontrado no catálogo")
        
        # Converter datas se fornecidas
        start_dt = None
        end_dt = None
        
        if start_date:
            try:
                start_dt = datetime.fromisoformat(start_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail="Formato de start_date inválido. Use YYYY-MM-DD")
        
        if end_date:
            try:
                end_dt = datetime.fromisoformat(end_date.replace('Z', '+00:00'))
            except ValueError:
                raise HTTPException(status_code=400, detail="Formato de end_date inválido. Use YYYY-MM-DD")
        
        # Se não especificou datas mas especificou period, calcular datas
        if not start_dt and not end_dt and period != "max":
            end_dt = datetime.utcnow()
            if period == "1mo":
                start_dt = end_dt - timedelta(days=30)
            elif period == "3mo":
                start_dt = end_dt - timedelta(days=90)
            elif period == "6mo":
                start_dt = end_dt - timedelta(days=180)
            elif period == "1y":
                start_dt = end_dt - timedelta(days=365)
            elif period == "2y":
                start_dt = end_dt - timedelta(days=730)
        
        # Buscar dados
        result = await get_ohlcv(
            session=session,
            ticker=ticker,
            start_date=start_dt,
            end_date=end_dt,
            limit=limit
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar dados OHLCV: {str(e)}")

@router.get("/dates/{ticker}")
async def get_available_dates_endpoint(
    ticker: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Retorna datas disponíveis para um ativo.
    
    **Parâmetros:**
    - `ticker`: Símbolo do ativo
    
    **Retorno:**
    ```json
    {
      "ticker": "PETR4",
      "dates": ["2024-01-15", "2024-01-12", "2024-01-11"],
      "count": 65
    }
    ```
    """
    try:
        # Validar que o ativo existe
        asset = await get_asset_by_ticker(session, ticker)
        if not asset:
            raise HTTPException(status_code=404, detail=f"Ativo {ticker} não encontrado")
        
        dates = await get_available_dates(session, ticker)
        
        return {
            "ticker": ticker.upper(),
            "dates": dates,
            "count": len(dates)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar datas: {str(e)}")

@router.post("/backfill")
async def backfill_ohlcv_endpoint(
    tickers: str = Query(..., description="Lista de tickers separados por vírgula"),
    range: str = Query("3mo", description="Período: 1mo, 3mo, 6mo, 1y, 2y"),
    interval: str = Query("1d", description="Intervalo: 1d, 1wk, 1mo"),
    max_concurrency: int = Query(3, ge=1, le=10, description="Máximo de requisições simultâneas"),
    session: AsyncSession = Depends(get_session),
):
    """
    Preenche dados históricos OHLCV para tickers específicos.
    
    **Atenção:** Consome requisições da API brapi. Use com moderação.
    
    **Parâmetros:**
    - `tickers`: Lista de símbolos (ex: PETR4,VALE3,MGLU3)
    - `range`: Período histórico
    - `interval`: Intervalo dos dados
    - `max_concurrency`: Controle de concorrência (respeita rate limit)
    
    **Retorno:**
    ```json
    {
      "message": "Backfill concluído",
      "stats": {
        "processed": 3,
        "inserted": 195,
        "updated": 0,
        "errors": 0,
        "total_requested": 3
      }
    }
    ```
    """
    try:
        # Validar e processar tickers
        ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
        if not ticker_list:
            raise HTTPException(status_code=400, detail="Nenhum ticker válido fornecido")
        
        # Validar que todos os tickers existem no catálogo
        invalid_tickers = []
        for ticker in ticker_list:
            asset = await get_asset_by_ticker(session, ticker)
            if not asset:
                invalid_tickers.append(ticker)
        
        if invalid_tickers:
            raise HTTPException(
                status_code=404, 
                detail=f"Tickers não encontrados no catálogo: {', '.join(invalid_tickers)}"
            )
        
        # Executar backfill
        stats = await backfill_ohlcv(
            session=session,
            tickers=ticker_list,
            range=range,
            interval=interval,
            max_concurrency=max_concurrency
        )
        
        return {
            "message": f"Backfill de {len(ticker_list)} tickers concluído",
            "stats": stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no backfill: {str(e)}")

@router.post("/update")
async def update_latest_endpoint(
    tickers: Optional[str] = Query(None, description="Lista de tickers separados por vírgula (opcional)"),
    max_concurrency: int = Query(3, ge=1, le=10, description="Máximo de requisições simultâneas"),
    session: AsyncSession = Depends(get_session),
):
    """
    Atualiza dados mais recentes para tickers.
    
    **Parâmetros:**
    - `tickers`: Lista específica de tickers (se não fornecido, atualiza todos)
    - `max_concurrency`: Controle de concorrência
    
    **Retorno:**
    ```json
    {
      "message": "Atualização concluída",
      "stats": {
        "processed": 50,
        "inserted": 50,
        "updated": 0,
        "errors": 0,
        "total_requested": 50
      }
    }
    ```
    """
    try:
        ticker_list = []
        
        if tickers:
            # Usar tickers específicos
            ticker_list = [t.strip().upper() for t in tickers.split(",") if t.strip()]
            if not ticker_list:
                raise HTTPException(status_code=400, detail="Nenhum ticker válido fornecido")
            
            # Validar que existem no catálogo
            invalid_tickers = []
            for ticker in ticker_list:
                asset = await get_asset_by_ticker(session, ticker)
                if not asset:
                    invalid_tickers.append(ticker)
            
            if invalid_tickers:
                raise HTTPException(
                    status_code=404, 
                    detail=f"Tickers não encontrados: {', '.join(invalid_tickers)}"
                )
        else:
            # Atualizar todos os ativos com dados OHLCV
            from sqlmodel import select, distinct
            query = select(distinct(QuoteOHLCV.ticker))
            result = await session.execute(query)
            ticker_list = result.scalars().all()
        
        if not ticker_list:
            return {"message": "Nenhum ticker para atualizar", "stats": {"processed": 0, "inserted": 0, "updated": 0, "errors": 0, "total_requested": 0}}
        
        # Executar atualização
        stats = await update_ohlcv_latest(
            session=session,
            tickers=ticker_list,
            max_concurrency=max_concurrency
        )
        
        return {
            "message": f"Atualização de {len(ticker_list)} tickers concluída",
            "stats": stats
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na atualização: {str(e)}")

# Import necessário para a rota update_latest
from app.models import QuoteOHLCV
