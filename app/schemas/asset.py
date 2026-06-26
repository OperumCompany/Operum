from pydantic import BaseModel


class Asset(BaseModel):
    ticker: str
    name: str
    asset_class: str
    country: str
    currency: str
    sector: str
    sub_type: str = ""
    source: str = "brapi"
