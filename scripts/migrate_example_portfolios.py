from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.portfolio_service import PortfolioService


def main() -> int:
    service = PortfolioService()
    service._ensure_schema()
    mode = "Postgres" if service.db.enabled else "local"
    print(f"Migração da Carteira Exemplo concluída no modo {mode}. Carteiras existentes permanecem padrão.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
