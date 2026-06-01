from datetime import datetime
from pydantic import BaseModel


class Position(BaseModel):
    asset_id: str
    ticker: str
    asset_class: str
    quantity: float
    avg_price: float | None = None
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
