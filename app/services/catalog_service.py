from typing import Any, List, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select, update, and_, or_, func
from sqlalchemy import desc
from app.core.cache import get_redis
from app.core.config import settings
from app.services.brapi_client import BrapiClient
from app.services.utils.key import make_cache_key
from app.services.utils.json_serializer import json_serializer, normalize_for_json
from app.models import ApiCall, Asset
from datetime import datetime, timezone
import json
import asyncio
import random
from brapi import NotFoundError

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

def _normalize_asset_type(asset_type: Optional[str]) -> Optional[str]:
    """Normaliza o tipo do ativo para valores padrão."""
    if not asset_type:
        return None
    
    type_lower = asset_type.lower().strip()
    
    # Retorna None para strings vazias
    if not type_lower:
        return None
    
    # Mapeamento de tipos (singular e plural)
    type_mapping = {
        "stock": "stock",
        "ação": "stock",
        "acao": "stock",
        "ações": "stock",
        "acoes": "stock",
        "fund": "fund",
        "fundo": "fund",
        "fundos": "fund",
        "fii": "fund",
        "bdr": "bdr",
        "etf": "etf",
        "index": "index",
        "índice": "index",
        "indice": "index",
    }
    
    return type_mapping.get(type_lower, type_lower)

def _extract_assets_from_list(payload: dict, default_type: Optional[str] = None) -> List[Asset]:
    """Extrai assets da resposta da API /available ou /quote/list."""
    results = payload.get("stocks") or payload.get("results") or []
    assets = []
    
    for item in results:
        if isinstance(item, str):
            ticker = item.upper().strip()
            asset = Asset(
                ticker=ticker,
                name=None,
                type=_normalize_asset_type(default_type) if default_type else None,
                sector=None,
                segment=None,
                isin=None,
                logo_url=None,
                raw={"symbol": ticker},
                updated_at=utcnow()
            )
        else:
            asset = Asset(
                ticker=(item.get("symbol") or item.get("stock") or "").upper().strip(),
                name=item.get("name") or item.get("shortName"),
                type=_normalize_asset_type(item.get("type") or default_type),
                sector=item.get("sector") or item.get("category"),
                segment=item.get("sector"),  # fallback
                isin=item.get("isin"),
                logo_url=item.get("logourl") or item.get("logoUrl"),
                raw=normalize_for_json(item),
                updated_at=utcnow()
            )
        
        # Apenas adicionar se tiver ticker válido
        if asset.ticker:
            assets.append(asset)
    
    return assets

def _needs_enrichment(asset: Asset) -> bool:
    """Determina se o ativo precisa de enriquecimento adicional."""
    if not asset.name:
        return True
    # Considera completo se tiver sector E logo_url (os principais campos enriquecidos)
    if asset.sector and asset.logo_url:
        return False
    if not asset.raw:
        return True
    if isinstance(asset.raw, dict) and set(asset.raw.keys()) == {"symbol"}:
        return True
    return False

async def _enrich_asset(asset: Asset, client: BrapiClient) -> None:
    """Busca detalhes adicionais do ativo via endpoint /quote."""
    if not _needs_enrichment(asset):
        return
    try:
        # Usar apenas fundamental=true para obter dados básicos do plano gratuito
        response = await client.quote([asset.ticker], {"fundamental": "true"})
    except NotFoundError:
        return
    except Exception as e:
        print(f"Não foi possível enriquecer {asset.ticker}: {e}")
        return
    items = (response.get("results") or response.get("stocks") or []) if isinstance(response, dict) else []
    if not items:
        return
    info = items[0]
    
    # Extrair dados básicos disponíveis no plano gratuito
    asset.name = info.get("longName") or info.get("shortName") or asset.name
    asset.type = _normalize_asset_type(info.get("type")) or asset.type
    asset.sector = info.get("sector") or asset.sector
    asset.segment = info.get("industry") or info.get("sector") or asset.segment
    asset.isin = info.get("isin") or info.get("isinCode") or asset.isin
    asset.logo_url = info.get("logourl") or info.get("logoUrl") or info.get("logo") or asset.logo_url
    
    # Salvar apenas os dados essenciais para não sobrecarregar o banco
    essential_fields = [
        "currency", "marketCap", "shortName", "longName", 
        "regularMarketChange", "regularMarketChangePercent", 
        "regularMarketTime", "regularMarketPrice", 
        "regularMarketDayHigh", "regularMarketDayRange", 
        "regularMarketDayLow", "regularMarketVolume", 
        "regularMarketPreviousClose", "regularMarketOpen", 
        "fiftyTwoWeekRange", "fiftyTwoWeekLow", "fiftyTwoWeekHigh", 
        "symbol", "logourl", "priceEarnings", "earningsPerShare"
    ]
    
    # Criar raw apenas com campos essenciais
    essential_raw = {}
    for field in essential_fields:
        if field in info:
            essential_raw[field] = info[field]
    
    asset.raw = essential_raw
    asset.updated_at = utcnow()
    # Aguardar levemente para respeitar rate limits do plano gratuito
    await asyncio.sleep(0.1)

async def _log_call(session: AsyncSession, *, endpoint: str, params: dict | None, cached: bool, status_code: int, response: dict | None = None, error: str | None = None, count: int = 0):
    """Registra chamada da API para observabilidade."""
    rec = ApiCall(
        endpoint=endpoint, 
        tickers=None, 
        params=normalize_for_json(params) if params else None, 
        cached=cached, 
        status_code=status_code, 
        error=error, 
        response=normalize_for_json(response) if response else None
    )
    session.add(rec)
    await session.commit()

async def sync_assets(session: AsyncSession, asset_type: str, limit: int = 100) -> Dict[str, Any]:
    """
    Sincroniza catálogo de ativos da brapi para o banco local.
    
    Args:
        session: Sessão do banco
        asset_type: Tipo de ativo (stock, fund, bdr, etf)
        limit: Limite de ativos por página
        
    Returns:
        Dict com estatísticas da sincronização
    """
    client = BrapiClient()
    stats = {
        "processed": 0,
        "inserted": 0,
        "updated": 0,
        "errors": 0,
        "pages": 0
    }
    
    try:
        page = 1
        has_more = True
        
        while has_more:
            params = {
                "page": page,
                "type": asset_type,
            }
            try:
                print(f"      -> Página {page}: solicitando catálogo ({asset_type})...", flush=True)
                payload = await client.available(params)
                stocks = payload.get("stocks") or payload.get("results") or []
                print(f"      -> Página {page}: recebidos {len(stocks)} símbolos", flush=True)
                await _log_call(
                    session,
                    endpoint="available",
                    params=params,
                    cached=False,
                    status_code=200,
                    response=payload,
                    count=len(stocks),
                )
                assets = _extract_assets_from_list(payload, default_type=asset_type)
                if not assets:
                    has_more = False
                    break
                for asset in assets:
                    try:
                        existing = await session.execute(select(Asset).where(Asset.ticker == asset.ticker))
                        existing_asset = existing.scalar_one_or_none()
                        if existing_asset:
                            existing_asset.name = asset.name
                            existing_asset.type = asset.type
                            existing_asset.sector = asset.sector
                            existing_asset.segment = asset.segment
                            existing_asset.isin = asset.isin
                            existing_asset.logo_url = asset.logo_url
                            existing_asset.raw = asset.raw
                            existing_asset.updated_at = utcnow()
                            stats["updated"] += 1
                            target_asset = existing_asset
                        else:
                            target_asset = asset
                            await _enrich_asset(target_asset, client)
                            session.add(target_asset)
                            stats["inserted"] += 1
                        
                        if _needs_enrichment(target_asset):
                            await _enrich_asset(target_asset, client)
                        stats["processed"] += 1
                        if stats["processed"] % 100 == 0:
                            print(
                                f"      -> Progresso: {stats['processed']} processados | {stats['inserted']} novos | {stats['updated']} atualizados",
                                flush=True,
                            )
                    except Exception as e:
                        stats["errors"] += 1
                        print(f"Error processing asset {asset.ticker}: {e}")
                await session.commit()
                stats["pages"] += 1
                print(
                    f"      -> Página {page} concluída (acumulado: {stats['processed']} processados)",
                    flush=True,
                )
                pagination = payload.get("pagination", {})
                has_more = bool(pagination.get("hasMore"))
                if has_more:
                    page += 1
                    await asyncio.sleep(0.5)
            except Exception as e:
                status_code = getattr(getattr(e, "response", None), "status_code", 500)
                await _log_call(
                    session,
                    endpoint="available",
                    params=params,
                    cached=False,
                    status_code=status_code,
                    error=str(e),
                )
                if status_code == 429:
                    await asyncio.sleep(2.0)
                    continue
                else:
                    raise e
    except Exception as e:
        stats["errors"] += 1
        print(f"Error in sync_assets: {e}")
        raise e
    
    return stats

async def list_assets(
    session: AsyncSession,
    asset_type: Optional[str] = None,
    sector: Optional[str] = None,
    search: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
    sort_by: str = "name"
) -> Dict[str, Any]:
    """
    Lista ativos do catálogo local com filtros e paginação.
    
    Args:
        session: Sessão do banco
        asset_type: Filtrar por tipo de ativo
        sector: Filtrar por setor
        search: Buscar por nome ou ticker
        page: Número da página
        limit: Itens por página
        sort_by: Ordenação (name, ticker, sector, updated_at)
        
    Returns:
        Dict com resultados paginados
    """
    # Cache curto para listagens
    r = await get_redis()
    cache_key = make_cache_key("catalog_v1", asset_type, sector, search, page, limit, sort_by)
    
    cached = await r.get(cache_key)
    if cached:
        return json.loads(cached)
    
    # Construir query
    query = select(Asset)
    count_query = select(func.count(Asset.id))
    
    # Aplicar filtros
    filters = []
    if asset_type:
        filters.append(Asset.type == asset_type.lower())
    if sector:
        filters.append(Asset.sector.ilike(f"%{sector}%"))
    if search:
        search_term = f"%{search}%"
        filters.append(
            or_(
                Asset.ticker.ilike(search_term),
                Asset.name.ilike(search_term)
            )
        )
    
    if filters:
        query = query.where(and_(*filters))
        count_query = count_query.where(and_(*filters))
    
    # Contar total
    total_result = await session.execute(count_query)
    total = total_result.scalar()
    
    # Ordenação
    if sort_by == "ticker":
        query = query.order_by(Asset.ticker)
    elif sort_by == "sector":
        query = query.order_by(Asset.sector, Asset.name)
    elif sort_by == "updated_at":
        query = query.order_by(desc(Asset.updated_at))
    else:
        query = query.order_by(Asset.name)
    
    # Paginação
    offset = (page - 1) * limit
    query = query.offset(offset).limit(limit)
    
    # Executar
    result = await session.execute(query)
    assets = result.scalars().all()
    
    # Serializar resposta
    response = {
        "assets": [
            {
                "ticker": asset.ticker,
                "name": asset.name,
                "type": asset.type,
                "sector": asset.sector,
                "segment": asset.segment,
                "isin": asset.isin,
                "logo_url": asset.logo_url,
                "updated_at": asset.updated_at.isoformat() if asset.updated_at else None
            }
            for asset in assets
        ],
        "pagination": {
            "page": page,
            "limit": limit,
            "total": total,
            "pages": (total + limit - 1) // limit
        }
    }
    
    # Cache por 5 minutos
    await r.setex(cache_key, 300, json.dumps(response, default=json_serializer))
    
    return response

async def get_asset_by_ticker(session: AsyncSession, ticker: str) -> Optional[Asset]:
    """
    Busca ativo específico por ticker.
    
    Args:
        session: Sessão do banco
        ticker: Símbolo do ativo
        
    Returns:
        Asset ou None se não encontrado
    """
    ticker = ticker.upper().strip()
    result = await session.execute(
        select(Asset).where(Asset.ticker == ticker)
    )
    return result.scalar_one_or_none()
