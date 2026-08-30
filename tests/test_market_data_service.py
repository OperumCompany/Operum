from app.services.market_data_service import MarketDataService


class _Response:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "indexes": [],
            "stocks": [
                {"stock": "ABEV3", "name": "AMBEV S.A.", "close": 14.92},
                {"stock": "ABEV3F", "name": "AMBEV S.A.", "close": 14.96},
            ],
        }


def test_brapi_public_list_fallback_uses_exact_symbol(monkeypatch):
    monkeypatch.setattr("app.services.market_data_service.requests.get", lambda *args, **kwargs: _Response())

    result = MarketDataService()._fetch_brapi_list_price("ABEV3")

    assert result is not None
    assert result["ticker"] == "ABEV3"
    assert result["price"] == 14.92
    assert result["currency"] == "BRL"
    assert result["source"] == "brapi-list"


def test_current_price_uses_public_list_before_yfinance(monkeypatch):
    service = MarketDataService()
    monkeypatch.setattr(service.storage, "load_json", lambda _key: None)
    monkeypatch.setattr(service.storage, "save_json", lambda _key, _value: None)
    monkeypatch.setattr(service, "_fetch_brapi_current_price", lambda _ticker: None)
    monkeypatch.setattr(
        service,
        "_fetch_brapi_list_price",
        lambda ticker: {"ticker": ticker, "price": 14.92},
    )
    monkeypatch.setattr(
        service,
        "_fetch_yfinance_current_price",
        lambda _ticker: (_ for _ in ()).throw(AssertionError("Yahoo should not be called")),
    )

    assert service.get_current_price("ABEV3") == {"ticker": "ABEV3", "price": 14.92}


def test_detailed_brapi_quote_is_skipped_without_token(monkeypatch):
    service = MarketDataService()
    service._brapi_token = ""
    monkeypatch.setattr(
        "app.services.market_data_service.requests.get",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("Brapi should not be called")),
    )

    assert service._fetch_brapi_current_price("ABEV3") is None


class _ChartResponse:
    def raise_for_status(self):
        return None

    def json(self):
        return {
            "chart": {
                "result": [{
                    "timestamp": [1_700_000_000, 1_700_086_400],
                    "indicators": {"quote": [{
                        "open": [14.0, 14.5],
                        "high": [15.0, 15.2],
                        "low": [13.9, 14.3],
                        "close": [14.8, 14.92],
                        "volume": [1000, 1200],
                    }]},
                }],
            },
        }


def test_yahoo_chart_history_parses_public_series(monkeypatch):
    monkeypatch.setattr("app.services.market_data_service.requests.get", lambda *args, **kwargs: _ChartResponse())

    result = MarketDataService()._fetch_yahoo_chart_history("ABEV3", "6mo", "1d")

    assert result is not None
    assert result["source"] == "yahoo-chart"
    assert len(result["prices"]) == 2
    assert result["prices"][-1]["close"] == 14.92
