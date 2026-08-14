from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, Field, field_validator


class Position(BaseModel):
    asset_id: str
    ticker: str
    asset_class: str
    quantity: float = Field(gt=0)
    avg_price: float | None = Field(default=None, ge=0)
    currency: str = "BRL"
    manual_notes: str = ""


class PortfolioSettings(BaseModel):
    risk_profile: str = "moderado"
    forecast_horizon_days: int = 5


class Portfolio(BaseModel):
    id: str
    owner_id: str | None = None
    name: str
    base_currency: str = "BRL"
    created_at: datetime
    updated_at: datetime
    positions: list[Position] = []
    settings: PortfolioSettings = PortfolioSettings()


class PortfolioCreate(BaseModel):
    name: str
    base_currency: str = "BRL"
    settings: PortfolioSettings = PortfolioSettings()


class PortfolioBulkDelete(BaseModel):
    portfolio_ids: list[str]


class PositionAdd(BaseModel):
    ticker: str
    asset_class: str
    quantity: float
    avg_price: float | None = None
    currency: str = "BRL"
    manual_notes: str = ""
    occurred_at: date | None = None

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("A data do aporte não pode estar no futuro")
        return value


class PortfolioTransaction(BaseModel):
    id: str
    portfolio_id: str
    ticker: str
    asset_class: str
    kind: Literal["opening", "buy", "close"]
    quantity_delta: float
    unit_price: float | None = None
    currency: str = "BRL"
    occurred_at: date
    created_at: datetime
    origin_key: str | None = None


class PortfolioHistoryPoint(BaseModel):
    date: str
    market_value: float | None
    invested_value: float | None
    quantity: float | None = None
    contribution_value: float | None = None
    contribution_quantity: float = 0.0


class PortfolioHistoryResponse(BaseModel):
    portfolio_id: str
    period: Literal["1m", "6m", "1y", "max"]
    ticker: str | None = None
    currency: str
    points: list[PortfolioHistoryPoint]
    available_tickers: list[str]
    warnings: list[str]
