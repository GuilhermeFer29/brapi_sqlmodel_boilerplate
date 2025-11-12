from __future__ import annotations
from typing import Optional
from sqlmodel import SQLModel, Field, Column, JSON
from sqlalchemy import UniqueConstraint, Index
from datetime import datetime, timezone

def utcnow() -> datetime:
    return datetime.now(timezone.utc)

class Asset(SQLModel, table=True):
    """
    Catálogo de ativos negociados na B3.
    Armazena informações básicas para organização por setor/tipo.
    """
    __tablename__ = "assets"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    ticker: str = Field(index=True, unique=True, max_length=32, description="Símbolo do ativo")
    name: Optional[str] = Field(default=None, index=True, max_length=255, description="Nome completo do ativo")
    type: Optional[str] = Field(default=None, index=True, max_length=32, description="Tipo: stock|fund|bdr|etf|index")
    sector: Optional[str] = Field(default=None, index=True, max_length=100, description="Setor econômico")
    segment: Optional[str] = Field(default=None, index=True, max_length=100, description="Segmento/Setor detalhado")
    isin: Optional[str] = Field(default=None, index=True, max_length=32, description="Código ISIN")
    logo_url: Optional[str] = Field(default=None, max_length=500, description="URL do logo")
    raw: Optional[dict] = Field(sa_column=Column(JSON), default=None, description="Dados brutos da API")
    created_at: datetime = Field(default_factory=utcnow, index=True)
    updated_at: datetime = Field(default_factory=utcnow, index=True)

class QuoteOHLCV(SQLModel, table=True):
    """
    Séries históricas de preços OHLCV.
    Armazena dados históricos para análise e gráficos.
    """
    __tablename__ = "quote_ohlcv"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    ticker: str = Field(index=True, max_length=32, description="Símbolo do ativo")
    date: datetime = Field(index=True, description="Data do pregão")
    open: Optional[float] = Field(default=None, description="Preço de abertura")
    high: Optional[float] = Field(default=None, description="Preço máximo")
    low: Optional[float] = Field(default=None, description="Preço mínimo")
    close: Optional[float] = Field(default=None, description="Preço de fechamento")
    volume: Optional[float] = Field(default=None, description="Volume negociado")
    adj_close: Optional[float] = Field(default=None, description="Preço ajustado")
    raw: Optional[dict] = Field(sa_column=Column(JSON), default=None, description="Dados brutos da API")

    __table_args__ = (
        UniqueConstraint("ticker", "date", name="uq_quote_ohlcv_ticker_date"),
        Index("ix_quote_ohlcv_ticker_date", "ticker", "date"),
    )

class Dividend(SQLModel, table=True):
    """
    Histórico de dividendos e proventos.
    Disponível apenas para alguns ativos no plano free.
    """
    __tablename__ = "dividends"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    ticker: str = Field(index=True, max_length=32, description="Símbolo do ativo")
    ex_date: Optional[datetime] = Field(default=None, index=True, description="Data ex-dividendo")
    payment_date: Optional[datetime] = Field(default=None, index=True, description="Data de pagamento")
    amount: Optional[float] = Field(default=None, description="Valor do dividendo")
    currency: Optional[str] = Field(default=None, max_length=16, description="Moeda do dividendo")
    type: Optional[str] = Field(default=None, max_length=32, description="Tipo: dividend|juros sobre capital")
    raw: Optional[dict] = Field(sa_column=Column(JSON), default=None, description="Dados brutos da API")

    __table_args__ = (
        UniqueConstraint("ticker", "ex_date", name="uq_dividends_ticker_ex_date"),
    )


class FinancialsTTM(SQLModel, table=True):
    """Dados financeiros TTM normalizados por ticker."""

    __tablename__ = "financials_ttm"

    id: Optional[int] = Field(default=None, primary_key=True)
    ticker: str = Field(index=True, unique=True, max_length=32, description="Símbolo do ativo")
    data: Optional[dict] = Field(sa_column=Column(JSON), default=None, description="Dados TTM normalizados")
    updated_at: datetime = Field(default_factory=utcnow, index=True)
