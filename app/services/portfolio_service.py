import threading
import uuid
from datetime import date, datetime, timezone

from app.core.config import SUPABASE_DB_SCHEMA
from app.db.postgres import PostgresClient
from app.schemas.portfolio import Portfolio, PortfolioCreate, Position, PositionAdd
from app.services.example_portfolio_service import EXAMPLE_VERSION, ExamplePortfolioService
from app.services.local_storage_service import LocalStorageService
from app.services.portfolio_transaction_service import PortfolioTransactionService


class PortfolioService:
    MAX_PORTFOLIOS = 50
    _example_lock = threading.Lock()

    def __init__(self):
        self.storage = LocalStorageService()
        self.db = PostgresClient(schema=SUPABASE_DB_SCHEMA)
        self._dir = "portfolios"
        self.examples = ExamplePortfolioService()
        self.transactions = PortfolioTransactionService(db=self.db, storage=self.storage)
        self._ensure_schema()
        self.transactions.ensure_schema()

    def _ensure_schema(self) -> None:
        if not self.db.enabled:
            return
        self.db.execute("alter table public.portfolios add column if not exists kind text not null default 'standard'")
        self.db.execute("alter table public.portfolios add column if not exists example_version integer")
        self.db.execute("create unique index if not exists idx_portfolios_one_example_per_owner on public.portfolios(owner_id) where kind = 'example'")

    def _row_to_portfolio(self, row: dict, positions: list[Position]) -> Portfolio:
        return Portfolio(
            id=row["id"],
            owner_id=row.get("owner_id"),
            name=row["name"],
            base_currency=row.get("base_currency", "BRL"),
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            kind=row.get("kind", "standard"),
            example_version=row.get("example_version"),
            positions=positions,
            settings={
                "risk_profile": row.get("risk_profile", "moderado"),
                "forecast_horizon_days": row.get("forecast_horizon_days", 5),
            },
        )

    def _load_positions_db(self, portfolio_id: str) -> list[Position]:
        rows = self.db.fetch_all(
            """
            select asset_id, ticker, asset_class, quantity, avg_price, currency, manual_notes
            from public.portfolio_positions
            where portfolio_id = %s::uuid
            order by ticker asc
            """,
            (portfolio_id,),
        )
        return [Position(**row) for row in rows]

    def list_all(self, user_id: str | None = None) -> list[Portfolio]:
        if self.db.enabled:
            if user_id:
                rows = self.db.fetch_all(
                    """
                    select id::text as id, owner_id::text as owner_id, name, base_currency,
                           risk_profile, forecast_horizon_days, created_at, updated_at, kind, example_version
                    from public.portfolios
                    where owner_id = %s::uuid
                    order by created_at desc
                    """,
                    (user_id,),
                )
            else:
                rows = self.db.fetch_all(
                    """
                    select id::text as id, owner_id::text as owner_id, name, base_currency,
                           risk_profile, forecast_horizon_days, created_at, updated_at, kind, example_version
                    from public.portfolios
                    order by created_at desc
                    """
                )
            return [self._row_to_portfolio(row, self._load_positions_db(row["id"])) for row in rows]

        files = self.storage.list_files(self._dir, ".json")
        portfolios = []
        for f in files:
            data = self.storage.load_json(f"{self._dir}/{f}")
            if data:
                portfolio = Portfolio(**data)
                if user_id and portfolio.owner_id not in (None, user_id):
                    continue
                portfolios.append(portfolio)
        return sorted(portfolios, key=lambda p: p.created_at, reverse=True)

    def get_by_id(self, portfolio_id: str, user_id: str | None = None) -> Portfolio | None:
        if self.db.enabled:
            if user_id:
                row = self.db.fetch_one(
                    """
                    select id::text as id, owner_id::text as owner_id, name, base_currency,
                           risk_profile, forecast_horizon_days, created_at, updated_at, kind, example_version
                    from public.portfolios
                    where id = %s::uuid and owner_id = %s::uuid
                    """,
                    (portfolio_id, user_id),
                )
            else:
                row = self.db.fetch_one(
                    """
                    select id::text as id, owner_id::text as owner_id, name, base_currency,
                           risk_profile, forecast_horizon_days, created_at, updated_at, kind, example_version
                    from public.portfolios
                    where id = %s::uuid
                    """,
                    (portfolio_id,),
                )
            if row is None:
                return None
            return self._row_to_portfolio(row, self._load_positions_db(portfolio_id))

        data = self.storage.load_json(f"{self._dir}/{portfolio_id}.json")
        if data is None:
            return None
        portfolio = Portfolio(**data)
        if user_id and portfolio.owner_id not in (None, user_id):
            return None
        return portfolio

    def create(self, data: PortfolioCreate, user_id: str | None = None) -> Portfolio:
        if len(self.list_all(user_id)) >= self.MAX_PORTFOLIOS:
            raise ValueError(f"Limite maximo de {self.MAX_PORTFOLIOS} carteiras atingido")

        now = datetime.now(timezone.utc)
        portfolio = Portfolio(
            id=str(uuid.uuid4()),
            owner_id=user_id,
            name=data.name,
            base_currency=data.base_currency,
            created_at=now,
            updated_at=now,
            settings=data.settings,
        )

        if self.db.enabled:
            self.db.execute(
                """
                insert into public.portfolios (
                    id, owner_id, name, base_currency, risk_profile, forecast_horizon_days, created_at, updated_at
                )
                values (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s)
                """,
                (
                    portfolio.id,
                    user_id,
                    portfolio.name,
                    portfolio.base_currency,
                    portfolio.settings.risk_profile,
                    portfolio.settings.forecast_horizon_days,
                    portfolio.created_at,
                    portfolio.updated_at,
                ),
            )
            return portfolio

        self.storage.save_json(f"{self._dir}/{portfolio.id}.json", portfolio.model_dump(mode="json"))
        return portfolio

    def create_example(self, user_id: str) -> tuple[Portfolio, bool]:
        with self._example_lock:
            return self._create_example_unlocked(user_id)

    def _create_example_unlocked(self, user_id: str) -> tuple[Portfolio, bool]:
        existing = next((item for item in self.list_all(user_id) if item.kind == "example"), None)
        if existing is not None:
            return existing, False
        if len(self.list_all(user_id)) >= self.MAX_PORTFOLIOS:
            raise ValueError(f"Limite maximo de {self.MAX_PORTFOLIOS} carteiras atingido")

        now = datetime.now(timezone.utc)
        portfolio = Portfolio(
            id=str(uuid.uuid4()), owner_id=user_id, name="Carteira Exemplo", base_currency="BRL",
            created_at=now, updated_at=now, kind="example", example_version=EXAMPLE_VERSION,
            positions=self.examples.template_positions(),
        )
        if self.db.enabled:
            created = False
            with self.db.transaction() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        """
                        insert into public.portfolios (
                            id, owner_id, name, base_currency, risk_profile, forecast_horizon_days,
                            created_at, updated_at, kind, example_version
                        ) values (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s)
                        on conflict (owner_id) where kind = 'example' do nothing
                        returning id::text as id
                        """,
                        (portfolio.id, user_id, portfolio.name, portfolio.base_currency,
                         portfolio.settings.risk_profile, portfolio.settings.forecast_horizon_days,
                         now, now, portfolio.kind, portfolio.example_version),
                    )
                    inserted = cursor.fetchone()
                    created = inserted is not None
                    if created:
                        for position in portfolio.positions:
                            cursor.execute(
                                """
                                insert into public.portfolio_positions (
                                    id, portfolio_id, asset_id, ticker, asset_class, quantity, avg_price,
                                    currency, manual_notes, created_at, updated_at
                                ) values (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                                """,
                                (str(uuid.uuid4()), portfolio.id, position.asset_id, position.ticker,
                                 position.asset_class, position.quantity, position.avg_price, position.currency,
                                 position.manual_notes, now, now),
                            )
                            cursor.execute(
                                """
                                insert into public.portfolio_transactions (
                                    id, portfolio_id, ticker, asset_class, kind, quantity_delta,
                                    unit_price, currency, occurred_at, created_at, origin_key
                                ) values (%s::uuid, %s::uuid, %s, %s, 'opening', %s, %s, %s, %s, %s, %s)
                                on conflict (origin_key) do nothing
                                """,
                                (str(uuid.uuid4()), portfolio.id, position.ticker, position.asset_class,
                                 position.quantity, position.avg_price, position.currency, date.today(), now,
                                 f"example-v{EXAMPLE_VERSION}:{portfolio.id}:{position.ticker}"),
                            )
            if not created:
                existing = next((item for item in self.list_all(user_id) if item.kind == "example"), None)
                if existing is None:
                    raise RuntimeError("Nao foi possivel localizar a Carteira Exemplo existente")
                return existing, False
            return portfolio, True
        self.storage.save_json(f"{self._dir}/{portfolio.id}.json", portfolio.model_dump(mode="json"))
        try:
            self.transactions.ensure_opening_transactions(portfolio, migration_date=date.today())
        except Exception:
            self.storage.delete_file(f"{self._dir}/{portfolio.id}.json")
            self.transactions.delete_for_portfolio(portfolio.id)
            raise
        return portfolio, True

    def update(self, portfolio_id: str, updates: dict, user_id: str | None = None) -> Portfolio | None:
        portfolio = self.get_by_id(portfolio_id, user_id)
        if portfolio is None:
            return None

        if self.db.enabled:
            next_name = updates.get("name", portfolio.name) or portfolio.name
            next_currency = updates.get("base_currency", portfolio.base_currency) or portfolio.base_currency
            next_settings = updates.get("settings") or {}
            next_risk = next_settings.get("risk_profile", portfolio.settings.risk_profile)
            next_horizon = next_settings.get("forecast_horizon_days", portfolio.settings.forecast_horizon_days)
            self.db.execute(
                """
                update public.portfolios
                set name = %s,
                    base_currency = %s,
                    risk_profile = %s,
                    forecast_horizon_days = %s,
                    updated_at = %s
                where id = %s::uuid and owner_id = %s::uuid
                """,
                (
                    next_name,
                    next_currency,
                    next_risk,
                    next_horizon,
                    datetime.now(timezone.utc),
                    portfolio_id,
                    user_id,
                ),
            )
            return self.get_by_id(portfolio_id, user_id)

        portfolio_dict = portfolio.model_dump(mode="json")
        for key, value in updates.items():
            if key == "settings" and isinstance(value, dict):
                portfolio_dict["settings"] = {**portfolio_dict["settings"], **value}
            elif value is not None and key in portfolio_dict:
                portfolio_dict[key] = value
        portfolio_dict["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.storage.save_json(f"{self._dir}/{portfolio_id}.json", portfolio_dict)
        return Portfolio(**portfolio_dict)

    def delete(self, portfolio_id: str, user_id: str | None = None) -> bool:
        portfolio = self.get_by_id(portfolio_id, user_id)
        if portfolio is None:
            return False
        if self.db.enabled:
            self.db.execute(
                "delete from public.portfolios where id = %s::uuid and owner_id = %s::uuid",
                (portfolio_id, user_id),
            )
            return True
        deleted = self.storage.delete_file(f"{self._dir}/{portfolio_id}.json")
        if deleted:
            self.transactions.delete_for_portfolio(portfolio_id)
        return deleted

    def delete_many(self, portfolio_ids: list[str], user_id: str | None = None) -> dict:
        unique_ids = list(dict.fromkeys(portfolio_ids))
        deleted_ids: list[str] = []
        missing_ids: list[str] = []

        for portfolio_id in unique_ids:
            if self.delete(portfolio_id, user_id):
                deleted_ids.append(portfolio_id)
            else:
                missing_ids.append(portfolio_id)

        return {
            "deleted_ids": deleted_ids,
            "missing_ids": missing_ids,
            "deleted_count": len(deleted_ids),
        }

    def add_position(self, portfolio_id: str, position_data: PositionAdd, user_id: str | None = None) -> Portfolio | None:
        portfolio = self.get_by_id(portfolio_id, user_id)
        if portfolio is None:
            return None
        self.transactions.ensure_opening_transactions(portfolio)
        occurred_at = position_data.occurred_at or date.today()

        if self.db.enabled:
            existing = self.db.fetch_one(
                """
                select id::text as id, quantity, avg_price, manual_notes
                from public.portfolio_positions
                where portfolio_id = %s::uuid and upper(ticker) = upper(%s)
                """,
                (portfolio_id, position_data.ticker),
            )
            now = datetime.now(timezone.utc)
            if existing:
                next_quantity = float(existing["quantity"]) + position_data.quantity
                existing_avg = float(existing["avg_price"]) if existing["avg_price"] is not None else None
                if existing_avg is not None and position_data.avg_price is not None:
                    next_avg_price = (
                        (float(existing["quantity"]) * existing_avg) + (position_data.quantity * position_data.avg_price)
                    ) / next_quantity
                elif existing_avg is None and float(existing["quantity"]) > 0:
                    next_avg_price = None
                else:
                    next_avg_price = position_data.avg_price
                next_notes = position_data.manual_notes or existing["manual_notes"] or ""
                self.db.execute(
                    """
                    update public.portfolio_positions
                    set quantity = %s,
                        avg_price = %s,
                        currency = %s,
                        manual_notes = %s,
                        updated_at = %s
                    where id = %s::uuid
                    """,
                    (next_quantity, next_avg_price, position_data.currency, next_notes, now, existing["id"]),
                )
            else:
                self.db.execute(
                    """
                    insert into public.portfolio_positions (
                        id, portfolio_id, asset_id, ticker, asset_class, quantity, avg_price, currency, manual_notes,
                        created_at, updated_at
                    )
                    values (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        str(uuid.uuid4()),
                        portfolio_id,
                        position_data.ticker,
                        position_data.ticker.upper(),
                        position_data.asset_class,
                        position_data.quantity,
                        position_data.avg_price,
                        position_data.currency,
                        position_data.manual_notes,
                        now,
                        now,
                    ),
                )
            self.db.execute(
                "update public.portfolios set updated_at = %s where id = %s::uuid and owner_id = %s::uuid",
                (now, portfolio_id, user_id),
            )
            self.transactions.append(
                portfolio_id, position_data.ticker, position_data.asset_class, "buy", position_data.quantity,
                position_data.avg_price, position_data.currency, occurred_at,
            )
            return self.get_by_id(portfolio_id, user_id)

        existing = [p for p in portfolio.positions if p.ticker.upper() == position_data.ticker.upper()]
        if existing:
            pos = existing[0]
            previous_quantity = pos.quantity
            previous_avg = pos.avg_price
            pos.quantity += position_data.quantity
            if previous_avg is not None and position_data.avg_price is not None:
                pos.avg_price = (
                    (previous_quantity * previous_avg) + (position_data.quantity * position_data.avg_price)
                ) / pos.quantity
            elif previous_avg is None and previous_quantity > 0:
                pos.avg_price = None
            else:
                pos.avg_price = position_data.avg_price
            if position_data.manual_notes:
                pos.manual_notes = position_data.manual_notes
        else:
            portfolio.positions.append(
                Position(
                    asset_id=position_data.ticker,
                    ticker=position_data.ticker.upper(),
                    asset_class=position_data.asset_class,
                    quantity=position_data.quantity,
                    avg_price=position_data.avg_price,
                    currency=position_data.currency,
                    manual_notes=position_data.manual_notes,
                )
            )

        portfolio.updated_at = datetime.now(timezone.utc)
        self.storage.save_json(f"{self._dir}/{portfolio_id}.json", portfolio.model_dump(mode="json"))
        self.transactions.append(
            portfolio_id, position_data.ticker, position_data.asset_class, "buy", position_data.quantity,
            position_data.avg_price, position_data.currency, occurred_at,
        )
        return portfolio

    def remove_position(self, portfolio_id: str, ticker: str, user_id: str | None = None) -> Portfolio | None:
        portfolio = self.get_by_id(portfolio_id, user_id)
        if portfolio is None:
            return None
        self.transactions.ensure_opening_transactions(portfolio)
        current_position = next((item for item in portfolio.positions if item.ticker.upper() == ticker.upper()), None)
        if current_position is not None:
            self.transactions.append(
                portfolio_id, current_position.ticker, current_position.asset_class, "close", -current_position.quantity,
                current_position.avg_price, current_position.currency, date.today(),
            )

        if self.db.enabled:
            self.db.execute(
                """
                delete from public.portfolio_positions
                where portfolio_id = %s::uuid and upper(ticker) = upper(%s)
                """,
                (portfolio_id, ticker),
            )
            self.db.execute(
                "update public.portfolios set updated_at = %s where id = %s::uuid and owner_id = %s::uuid",
                (datetime.now(timezone.utc), portfolio_id, user_id),
            )
            return self.get_by_id(portfolio_id, user_id)

        portfolio.positions = [p for p in portfolio.positions if p.ticker.upper() != ticker.upper()]
        portfolio.updated_at = datetime.now(timezone.utc)
        self.storage.save_json(f"{self._dir}/{portfolio_id}.json", portfolio.model_dump(mode="json"))
        return portfolio
