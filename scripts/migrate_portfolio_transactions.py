from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.portfolio_service import PortfolioService


def main() -> int:
    service = PortfolioService()
    service.transactions.ensure_schema()
    portfolios = service.list_all()
    created = 0
    for portfolio in portfolios:
        created += service.transactions.ensure_opening_transactions(portfolio)
    mode = "Postgres" if service.db.enabled else "local"
    print(f"Migração concluída no modo {mode}: {created} saldos iniciais criados em {len(portfolios)} carteiras.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
