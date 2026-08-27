from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone

from app.core.config import SUPABASE_DB_SCHEMA
from app.db.postgres import PostgresClient
from app.schemas.portfolio import Portfolio, PortfolioTransaction
from app.services.local_storage_service import LocalStorageService
from app.services.market_data_service import MarketDataService


PERIOD_DAYS = {"1m": 30, "6m": 183, "1y": 365}


class PortfolioTransactionService:
    def __init__(
        self,
        db: PostgresClient | None = None,
        storage: LocalStorageService | None = None,
        market: MarketDataService | None = None,
    ):
        self.db = db or PostgresClient(schema=SUPABASE_DB_SCHEMA)
        self.storage = storage or LocalStorageService()
        self.market = market or MarketDataService()
        self._dir = "portfolio_transactions"

    def _path(self, portfolio_id: str) -> str:
        return f"{self._dir}/{portfolio_id}.json"

    def ensure_schema(self) -> None:
        if not self.db.enabled:
            return
        self.db.execute(
            """
            create table if not exists public.portfolio_transactions (
              id uuid primary key default gen_random_uuid(),
              portfolio_id uuid not null references public.portfolios(id) on delete cascade,
              ticker text not null,
              asset_class text not null,
              kind text not null check (kind in ('opening', 'buy', 'close')),
              quantity_delta numeric(20, 8) not null check (quantity_delta <> 0),
              unit_price numeric(20, 8),
              currency text not null default 'BRL',
              occurred_at date not null,
              origin_key text unique,
              created_at timestamptz not null default timezone('utc', now())
            )
            """
        )
        self.db.execute(
            "create index if not exists idx_portfolio_transactions_portfolio_date on public.portfolio_transactions(portfolio_id, occurred_at)"
        )
        self.db.execute(
            "create index if not exists idx_portfolio_transactions_ticker on public.portfolio_transactions(portfolio_id, ticker)"
        )
        self.db.execute("alter table public.portfolio_transactions enable row level security")
        self.db.execute("revoke all privileges on table public.portfolio_transactions from anon, authenticated")

    def list_for_portfolio(self, portfolio_id: str) -> list[PortfolioTransaction]:
        if self.db.enabled:
            rows = self.db.fetch_all(
                """
                select id::text as id, portfolio_id::text as portfolio_id, ticker, asset_class, kind,
                       quantity_delta, unit_price, currency, occurred_at, created_at, origin_key
                from public.portfolio_transactions
                where portfolio_id = %s::uuid
                order by occurred_at asc, created_at asc
                """,
                (portfolio_id,),
            )
            return [PortfolioTransaction(**row) for row in rows]
        payload = self.storage.load_json(self._path(portfolio_id)) or []
        return sorted(
            [PortfolioTransaction(**item) for item in payload],
            key=lambda item: (item.occurred_at, item.created_at),
        )

    def delete_for_portfolio(self, portfolio_id: str) -> None:
        if not self.db.enabled:
            self.storage.delete_file(self._path(portfolio_id))

    def append(
        self,
        portfolio_id: str,
        ticker: str,
        asset_class: str,
        kind: str,
        quantity_delta: float,
        unit_price: float | None,
        currency: str,
        occurred_at: date,
        origin_key: str | None = None,
    ) -> PortfolioTransaction:
        now = datetime.now(timezone.utc)
        transaction = PortfolioTransaction(
            id=str(uuid.uuid4()),
            portfolio_id=portfolio_id,
            ticker=ticker.upper(),
            asset_class=asset_class,
            kind=kind,
            quantity_delta=quantity_delta,
            unit_price=unit_price,
            currency=currency,
            occurred_at=occurred_at,
            created_at=now,
            origin_key=origin_key,
        )
        if self.db.enabled:
            self.db.execute(
                """
                insert into public.portfolio_transactions
                  (id, portfolio_id, ticker, asset_class, kind, quantity_delta, unit_price, currency, occurred_at, origin_key, created_at)
                values (%s::uuid, %s::uuid, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                on conflict (origin_key) do nothing
                """,
                (
                    transaction.id, portfolio_id, transaction.ticker, asset_class, kind, quantity_delta,
                    unit_price, currency, occurred_at, origin_key, now,
                ),
            )
        else:
            existing = self.storage.load_json(self._path(portfolio_id)) or []
            if origin_key and any(item.get("origin_key") == origin_key for item in existing):
                return next(PortfolioTransaction(**item) for item in existing if item.get("origin_key") == origin_key)
            existing.append(transaction.model_dump(mode="json"))
            self.storage.save_json(self._path(portfolio_id), existing)
        return transaction

    def ensure_opening_transactions(self, portfolio: Portfolio, migration_date: date | None = None) -> int:
        migration_date = migration_date or date.today()
        existing_transactions = self.list_for_portfolio(portfolio.id)
        existing_keys = {item.origin_key for item in existing_transactions if item.origin_key}
        existing_tickers = {item.ticker.upper() for item in existing_transactions}
        created = 0
        for position in portfolio.positions:
            origin_key = f"legacy-position:{portfolio.id}:{position.ticker.upper()}"
            if origin_key in existing_keys or position.ticker.upper() in existing_tickers:
                continue
            self.append(
                portfolio.id,
                position.ticker,
                position.asset_class,
                "opening",
                position.quantity,
                position.avg_price,
                position.currency,
                migration_date,
                origin_key,
            )
            created += 1
        return created

    @staticmethod
    def _start_date(period: str, transactions: list[PortfolioTransaction]) -> date:
        today = date.today()
        if period == "max":
            return min((item.occurred_at for item in transactions), default=today)
        return today - timedelta(days=PERIOD_DAYS[period])

    def build_history(self, portfolio: Portfolio, period: str, ticker: str | None = None) -> dict:
        transactions = self.list_for_portfolio(portfolio.id)
        selected_ticker = ticker.upper() if ticker else None
        if selected_ticker:
            transactions = [item for item in transactions if item.ticker.upper() == selected_ticker]
        start_date = self._start_date(period, transactions)
        end_date = date.today()
        all_tickers = sorted({item.ticker.upper() for item in self.list_for_portfolio(portfolio.id)})
        target_tickers = [selected_ticker] if selected_ticker else all_tickers
        warnings: list[str] = []
        histories: dict[str, dict[date, float]] = {}
        market_period = {"1m": "1mo", "6m": "6mo", "1y": "1y", "max": "max"}[period]

        for symbol in target_tickers:
            result = self.market.get_history(symbol, period=market_period, interval="1d")
            values: dict[date, float] = {}
            for point in (result or {}).get("prices", []):
                try:
                    point_date = date.fromisoformat(str(point.get("date", ""))[:10])
                    values[point_date] = float(point.get("close"))
                except (TypeError, ValueError):
                    continue
            if not values:
                warnings.append(f"Histórico de preço indisponível para {symbol}.")
            histories[symbol] = values

        relevant_dates = {start_date, end_date}
        for values in histories.values():
            relevant_dates.update(day for day in values if start_date <= day <= end_date)
        relevant_dates.update(item.occurred_at for item in transactions if start_date <= item.occurred_at <= end_date)
        dates = sorted(relevant_dates)
        state: dict[str, dict[str, float | None]] = {
            symbol: {"quantity": 0.0, "cost": 0.0, "last_price": None} for symbol in target_tickers
        }
        tx_index = 0
        ordered_transactions = sorted(transactions, key=lambda item: (item.occurred_at, item.created_at))
        points: list[dict] = []
        unknown_cost_symbols: set[str] = set()

        for day in dates:
            day_contribution = 0.0
            day_contribution_known = True
            day_quantity = 0.0
            while tx_index < len(ordered_transactions) and ordered_transactions[tx_index].occurred_at <= day:
                item = ordered_transactions[tx_index]
                tx_index += 1
                symbol_state = state.setdefault(item.ticker, {"quantity": 0.0, "cost": 0.0, "last_price": None})
                previous_quantity = float(symbol_state["quantity"] or 0.0)
                previous_cost = symbol_state["cost"]
                delta = float(item.quantity_delta)
                is_visible_movement = item.occurred_at == day
                if delta > 0:
                    if item.unit_price is None or previous_cost is None:
                        symbol_state["cost"] = None
                        unknown_cost_symbols.add(item.ticker)
                        if is_visible_movement:
                            day_contribution_known = False
                    else:
                        addition = delta * float(item.unit_price)
                        symbol_state["cost"] = float(previous_cost) + addition
                        if is_visible_movement:
                            day_contribution += addition
                else:
                    if previous_cost is not None and previous_quantity > 0:
                        reduction = min(abs(delta), previous_quantity) * (float(previous_cost) / previous_quantity)
                        symbol_state["cost"] = max(0.0, float(previous_cost) - reduction)
                        if is_visible_movement:
                            day_contribution -= reduction
                    else:
                        if is_visible_movement:
                            day_contribution_known = False
                    if previous_quantity + delta <= 0:
                        symbol_state["cost"] = 0.0
                symbol_state["quantity"] = max(0.0, previous_quantity + delta)
                if is_visible_movement:
                    day_quantity += delta

            market_total = 0.0
            market_known = False
            invested_total = 0.0
            invested_known = True
            total_quantity = 0.0
            for symbol, symbol_state in state.items():
                if day in histories.get(symbol, {}):
                    symbol_state["last_price"] = histories[symbol][day]
                quantity = float(symbol_state["quantity"] or 0.0)
                total_quantity += quantity
                if quantity > 0 and symbol_state["last_price"] is not None:
                    market_total += quantity * float(symbol_state["last_price"])
                    market_known = True
                if quantity > 0 and symbol_state["cost"] is None:
                    invested_known = False
                elif symbol_state["cost"] is not None:
                    invested_total += float(symbol_state["cost"])

            points.append({
                "date": day.isoformat(),
                "market_value": round(market_total, 2) if market_known or total_quantity == 0 else None,
                "invested_value": round(invested_total, 2) if invested_known else None,
                "quantity": round(total_quantity, 8) if selected_ticker else None,
                "contribution_value": round(day_contribution, 2) if day_contribution_known and day_quantity != 0 else None,
                "contribution_quantity": round(day_quantity, 8),
            })

        if unknown_cost_symbols:
            warnings.append(f"Custo investido indisponível para: {', '.join(sorted(unknown_cost_symbols))}.")
        return {
            "portfolio_id": portfolio.id,
            "period": period,
            "ticker": selected_ticker,
            "currency": portfolio.base_currency,
            "points": points,
            "available_tickers": all_tickers,
            "warnings": warnings,
        }
