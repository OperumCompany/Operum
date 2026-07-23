from fastapi import APIRouter, HTTPException

from app.schemas.asset import Asset
from app.services.asset_universe_service import AssetUniverseService

router = APIRouter(prefix="/assets", tags=["assets"])
service = AssetUniverseService()


@router.get("/universe", response_model=list[Asset])
def list_universe():
    return service.get_all()


@router.get("/search", response_model=list[Asset])
def search_assets(q: str = ""):
    if not q or len(q.strip()) < 2:
        return []
    return service.search(q)


@router.get("/{ticker}", response_model=Asset)
def get_asset(ticker: str):
    asset = service.get_by_ticker(ticker)
    if asset is None:
        raise HTTPException(status_code=404, detail="Ativo não encontrado")
    return asset
