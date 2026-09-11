from datetime import date, datetime
from typing import Literal
from pydantic import Field, field_validator

from app.schemas.base import StrictBaseModel


class Position(StrictBaseModel):
    asset_id: str = Field(min_length=1, max_length=32)
    ticker: str = Field(min_length=1, max_length=16, pattern=r"^[A-Za-z0-9.=-]+$")
    asset_class: str = Field(min_length=1, max_length=32)
    quantity: float = Field(gt=0)
    avg_price: float | None = Field(default=None, ge=0)
    currency: str = Field(default="BRL", min_length=3, max_length=3)
    manual_notes: str = Field(default="", max_length=500)


class PortfolioSettings(StrictBaseModel):
    risk_profile: str = Field(default="moderado", min_length=3, max_length=30)
    forecast_horizon_days: int = Field(default=5, ge=1, le=365)


class Portfolio(StrictBaseModel):
    id: str
    owner_id: str | None = None
    name: str
    base_currency: str = "BRL"
    created_at: datetime
    updated_at: datetime
    kind: Literal["standard", "example"] = "standard"
    example_version: int | None = None
    positions: list[Position] = []
    settings: PortfolioSettings = PortfolioSettings()


class PortfolioCreate(StrictBaseModel):
    name: str = Field(min_length=1, max_length=120)
    base_currency: str = Field(default="BRL", min_length=3, max_length=3)
    settings: PortfolioSettings = PortfolioSettings()


class PortfolioSettingsUpdate(StrictBaseModel):
    risk_profile: str | None = Field(default=None, min_length=3, max_length=30)
    forecast_horizon_days: int | None = Field(default=None, ge=1, le=365)


class PortfolioUpdate(StrictBaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    base_currency: str | None = Field(default=None, min_length=3, max_length=3)
    settings: PortfolioSettingsUpdate | None = None


class ExamplePortfolioCreateResponse(StrictBaseModel):
    portfolio: Portfolio
    created: bool


class PortfolioBulkDelete(StrictBaseModel):
    portfolio_ids: list[str] = Field(min_length=1, max_length=50)


class PositionAdd(StrictBaseModel):
    ticker: str = Field(min_length=1, max_length=16, pattern=r"^[A-Za-z0-9.=-]+$")
    asset_class: str = Field(min_length=1, max_length=32)
    quantity: float = Field(gt=0)
    avg_price: float | None = Field(default=None, ge=0)
    currency: str = Field(default="BRL", min_length=3, max_length=3)
    manual_notes: str = Field(default="", max_length=500)
    occurred_at: date | None = None

    @field_validator("occurred_at")
    @classmethod
    def validate_occurred_at(cls, value: date | None) -> date | None:
        if value is not None and value > date.today():
            raise ValueError("A data do aporte não pode estar no futuro")
        return value


class PortfolioTransaction(StrictBaseModel):
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


class PortfolioHistoryPoint(StrictBaseModel):
    date: str
    market_value: float | None
    invested_value: float | None
    quantity: float | None = None
    contribution_value: float | None = None
    contribution_quantity: float = 0.0


class PortfolioHistoryResponse(StrictBaseModel):
    portfolio_id: str
    period: Literal["1m", "6m", "1y", "max"]
    ticker: str | None = None
    currency: str
    points: list[PortfolioHistoryPoint]
    available_tickers: list[str]
    warnings: list[str]
