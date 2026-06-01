import uuid
from datetime import datetime, timezone
from app.services.local_storage_service import LocalStorageService
from app.schemas.portfolio import Portfolio, PortfolioCreate, Position, PositionAdd, PortfolioSettings


class PortfolioService:
    MAX_PORTFOLIOS = 50

    def __init__(self):
        self.storage = LocalStorageService()
        self._dir = "portfolios"

    def list_all(self) -> list[Portfolio]:
        files = self.storage.list_files(self._dir, ".json")
        portfolios = []
        for f in files:
            data = self.storage.load_json(f"{self._dir}/{f}")
            if data:
                portfolios.append(Portfolio(**data))
        return sorted(portfolios, key=lambda p: p.created_at, reverse=True)

    def get_by_id(self, portfolio_id: str) -> Portfolio | None:
        data = self.storage.load_json(f"{self._dir}/{portfolio_id}.json")
        if data is None:
            return None
        return Portfolio(**data)

    def create(self, data: PortfolioCreate) -> Portfolio:
        if len(self.list_all()) >= self.MAX_PORTFOLIOS:
            raise ValueError(f"Limite maximo de {self.MAX_PORTFOLIOS} carteiras atingido")

        now = datetime.now(timezone.utc)
        portfolio = Portfolio(
            id=str(uuid.uuid4()),
            name=data.name,
            base_currency=data.base_currency,
            created_at=now,
            updated_at=now,
            settings=data.settings,
        )
        self.storage.save_json(f"{self._dir}/{portfolio.id}.json", portfolio.model_dump(mode="json"))
        return portfolio

    def update(self, portfolio_id: str, updates: dict) -> Portfolio | None:
        portfolio = self.get_by_id(portfolio_id)
        if portfolio is None:
            return None
        portfolio_dict = portfolio.model_dump(mode="json")
        for key, value in updates.items():
            if value is not None and key in portfolio_dict:
                portfolio_dict[key] = value
        portfolio_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.storage.save_json(f"{self._dir}/{portfolio_id}.json", portfolio_dict)
        return Portfolio(**portfolio_dict)

    def delete(self, portfolio_id: str) -> bool:
        return self.storage.delete_file(f"{self._dir}/{portfolio_id}.json")

    def delete_many(self, portfolio_ids: list[str]) -> dict:
        unique_ids = list(dict.fromkeys(portfolio_ids))
        deleted_ids: list[str] = []
        missing_ids: list[str] = []

        for portfolio_id in unique_ids:
            if self.delete(portfolio_id):
                deleted_ids.append(portfolio_id)
            else:
                missing_ids.append(portfolio_id)

        return {
            "deleted_ids": deleted_ids,
            "missing_ids": missing_ids,
            "deleted_count": len(deleted_ids),
        }

    def add_position(self, portfolio_id: str, position_data: PositionAdd) -> Portfolio | None:
        portfolio = self.get_by_id(portfolio_id)
        if portfolio is None:
            return None

        existing = [p for p in portfolio.positions if p.ticker.upper() == position_data.ticker.upper()]
        if existing:
            pos = existing[0]
            pos.quantity += position_data.quantity
            if position_data.avg_price is not None:
                pos.avg_price = position_data.avg_price
            if position_data.manual_notes:
                pos.manual_notes = position_data.manual_notes
        else:
            new_pos = Position(
                asset_id=position_data.ticker,
                ticker=position_data.ticker.upper(),
                asset_class=position_data.asset_class,
                quantity=position_data.quantity,
                avg_price=position_data.avg_price,
                currency=position_data.currency,
                manual_notes=position_data.manual_notes,
            )
            portfolio.positions.append(new_pos)

        portfolio.updated_at = datetime.now(timezone.utc)
        self.storage.save_json(f"{self._dir}/{portfolio_id}.json", portfolio.model_dump(mode="json"))
        return portfolio

    def remove_position(self, portfolio_id: str, ticker: str) -> Portfolio | None:
        portfolio = self.get_by_id(portfolio_id)
        if portfolio is None:
            return None

        portfolio.positions = [p for p in portfolio.positions if p.ticker.upper() != ticker.upper()]
        portfolio.updated_at = datetime.now(timezone.utc)
        self.storage.save_json(f"{self._dir}/{portfolio_id}.json", portfolio.model_dump(mode="json"))
        return portfolio
