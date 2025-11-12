from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.session import get_session
from app.services.catalog_service import list_assets, sync_assets, get_asset_by_ticker

router = APIRouter(prefix="/api/catalog", tags=["catalog"])

@router.get("/assets")
async def get_assets(
    type: Optional[str] = Query(None, description="Tipo de ativo: stock, fund, bdr, etf, index"),
    sector: Optional[str] = Query(None, description="Filtrar por setor"),
    search: Optional[str] = Query(None, description="Buscar por nome ou ticker"),
    page: int = Query(1, ge=1, description="Número da página"),
    limit: int = Query(50, ge=1, le=100, description="Itens por página (máx 100)"),
    sort_by: str = Query("name", description="Ordenação: name, ticker, sector, updated_at"),
    session: AsyncSession = Depends(get_session),
):
    """
    Lista catálogo de ativos com filtros e paginação.
    
    **Parâmetros:**
    - `type`: Filtrar por tipo de ativo (stock, fund, bdr, etf, index)
    - `sector`: Filtrar por setor econômico
    - `search`: Buscar por nome ou ticker (case insensitive)
    - `page`: Número da página (inicia em 1)
    - `limit`: Itens por página (1-100)
    - `sort_by`: Ordenação dos resultados
    
    **Retorno:**
    ```json
    {
      "assets": [
        {
          "ticker": "PETR4",
          "name": "PETROBRAS PN",
          "type": "stock",
          "sector": "Petróleo, Gás e Biocombustíveis",
          "segment": "Petróleo, Gás e Biocombustíveis",
          "isin": "BRPETRACNOR11",
          "logo_url": "https://icons.brapi.dev/logos/PETR4.png",
          "updated_at": "2024-01-15T10:30:00Z"
        }
      ],
      "pagination": {
        "page": 1,
        "limit": 50,
        "total": 1250,
        "pages": 25
      }
    }
    ```
    """
    try:
        result = await list_assets(
            session=session,
            asset_type=type,
            sector=sector,
            search=search,
            page=page,
            limit=limit,
            sort_by=sort_by
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar ativos: {str(e)}")

@router.get("/assets/{ticker}")
async def get_asset(
    ticker: str,
    session: AsyncSession = Depends(get_session),
):
    """
    Busca ativo específico por ticker.
    
    **Parâmetros:**
    - `ticker`: Símbolo do ativo (ex: PETR4, VALE3)
    
    **Retorno:**
    ```json
    {
      "ticker": "PETR4",
      "name": "PETROBRAS PN",
      "type": "stock",
      "sector": "Petróleo, Gás e Biocombustíveis",
      "segment": "Petróleo, Gás e Biocombustíveis",
      "isin": "BRPETRACNOR11",
      "logo_url": "https://icons.brapi.dev/logos/PETR4.png",
      "updated_at": "2024-01-15T10:30:00Z"
    }
    ```
    """
    try:
        asset = await get_asset_by_ticker(session, ticker)
        if not asset:
            raise HTTPException(status_code=404, detail=f"Ativo {ticker} não encontrado")
        
        return {
            "ticker": asset.ticker,
            "name": asset.name,
            "type": asset.type,
            "sector": asset.sector,
            "segment": asset.segment,
            "isin": asset.isin,
            "logo_url": asset.logo_url,
            "updated_at": asset.updated_at.isoformat() if asset.updated_at else None
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar ativo: {str(e)}")

@router.post("/sync/{asset_type}")
async def sync_assets_endpoint(
    asset_type: str,
    limit: int = Query(100, ge=1, le=1000, description="Limite de ativos por página"),
    session: AsyncSession = Depends(get_session),
):
    """
    Sincroniza catálogo de ativos da brapi para o banco local.
    
    **Parâmetros:**
    - `asset_type`: Tipo de ativo para sincronizar (stock, fund, bdr, etf)
    - `limit`: Limite de ativos por requisição (1-1000)
    
    **Retorno:**
    ```json
    {
      "message": "Sincronização concluída",
      "stats": {
        "processed": 450,
        "inserted": 450,
        "updated": 0,
        "errors": 0,
        "pages": 5
      }
    }
    ```
    """
    try:
        # Validar tipo de ativo
        valid_types = ["stock", "fund", "bdr", "etf", "index"]
        if asset_type not in valid_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Tipo de ativo inválido. Use: {', '.join(valid_types)}"
            )
        
        stats = await sync_assets(session, asset_type, limit)
        
        return {
            "message": f"Sincronização de {asset_type} concluída",
            "stats": stats
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na sincronização: {str(e)}")

@router.get("/types")
async def get_asset_types():
    """
    Retorna lista de tipos de ativos disponíveis.
    
    **Retorno:**
    ```json
    {
      "types": [
        {"value": "stock", "label": "Ações"},
        {"value": "fund", "label": "Fundos Imobiliários"},
        {"value": "bdr", "label": "BDRs"},
        {"value": "etf", "label": "ETFs"},
        {"value": "index", "label": "Índices"}
      ]
    }
    ```
    """
    return {
        "types": [
            {"value": "stock", "label": "Ações"},
            {"value": "fund", "label": "Fundos Imobiliários (FIIs)"},
            {"value": "bdr", "label": "BDRs"},
            {"value": "etf", "label": "ETFs"},
            {"value": "index", "label": "Índices"}
        ]
    }

@router.get("/sectors")
async def get_sectors(
    session: AsyncSession = Depends(get_session),
):
    """
    Retorna lista de setores disponíveis no catálogo.
    
    **Retorno:**
    ```json
    {
      "sectors": [
        {"value": "Petróleo, Gás e Biocombustíveis", "count": 45},
        {"value": "Financeiro", "count": 120},
        {"value": "Tecnologia", "count": 35}
      ]
    }
    ```
    """
    try:
        from sqlmodel import select, func
        
        # Buscar setores distintos e contagem
        query = (
            select(Asset.sector, func.count(Asset.id).label("count"))
            .where(Asset.sector.isnot(None))
            .group_by(Asset.sector)
            .order_by(func.count(Asset.id).desc())
        )
        
        result = await session.execute(query)
        sectors = result.all()
        
        return {
            "sectors": [
                {"value": sector, "count": count}
                for sector, count in sectors if sector
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao buscar setores: {str(e)}")
