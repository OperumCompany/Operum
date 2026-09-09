from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from app.ml.providers import (
    B3PublicSourceAdapter,
    BCBPublicSourceAdapter,
    CVMPublicSourceAdapter,
    IBGEPublicSourceAdapter,
    ReconciliationError,
    SourceUnavailableError,
    YahooDatasetProvider,
    normalize_yahoo_chart_payload,
    normalize_yfinance_history,
    reconcile_yahoo_fallback,
)


FIXTURES = Path(__file__).parent / "fixtures" / "ml"


def test_normalize_yfinance_history_rejects_missing_adjusted_and_action_evidence():
    index = pd.to_datetime(["2024-01-02", "2024-01-03"])
    raw = pd.DataFrame(
        {
            "Open": [10.0, 11.0],
            "High": [11.0, 12.0],
            "Low": [9.0, 10.0],
            "Close": [10.5, 11.5],
            "Volume": [1000, 1200],
        },
        index=index,
    )

    with pytest.raises(ValueError, match="adjusted/action evidence"):
        normalize_yfinance_history(raw, ticker="PETR4", asset_class="BR_STOCK")


def test_normalize_yfinance_history_accepts_single_ticker_multiindex():
    raw = pd.DataFrame(
        [[10.0, 11.0, 9.0, 10.5, 10.5, 1000, 0.0, 0.0]],
        index=pd.to_datetime(["2024-01-02"]),
        columns=pd.MultiIndex.from_product(
            [
                [
                    "Open",
                    "High",
                    "Low",
                    "Close",
                    "Adj Close",
                    "Volume",
                    "Stock Splits",
                    "Dividends",
                ],
                ["PETR4.SA"],
            ]
        ),
    )

    result = normalize_yfinance_history(raw, ticker="PETR4", asset_class="BR_STOCK")

    assert len(result) == 1
    assert result.iloc[0]["volume"] == 1000


def test_normalize_yfinance_history_separates_split_and_total_adjustment():
    raw = pd.DataFrame(
        {
            "Open": [100.0, 52.0],
            "High": [102.0, 53.0],
            "Low": [99.0, 51.0],
            "Close": [100.0, 52.0],
            "Adj Close": [48.0, 52.0],
            "Volume": [1000, 2200],
            "Stock Splits": [0.0, 2.0],
            "Dividends": [0.0, 0.0],
        },
        index=pd.to_datetime(["2024-01-02", "2024-01-03"]),
    )

    result = normalize_yfinance_history(raw, ticker="PETR4", asset_class="BR_STOCK")

    assert result["raw_close"].tolist() == [100.0, 52.0]
    assert result["split_adjusted_close"].tolist() == [50.0, 52.0]
    assert result["total_return_index"].tolist() == [48.0, 52.0]
    assert result["close"].tolist() == [48.0, 52.0]


def test_yahoo_chart_accepts_explicit_complete_no_action_evidence():
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [1704153600],
                    "events": {},
                    "indicators": {
                        "quote": [{"open": [100], "high": [110], "low": [90], "close": [100], "volume": [1000]}],
                        "adjclose": [{"adjclose": [50]}],
                    },
                }
            ]
        }
    }

    result = normalize_yahoo_chart_payload(payload, ticker="PETR4", asset_class="BR_STOCK")

    assert result.iloc[0]["open"] == 50
    assert result.iloc[0]["high"] == 55
    assert result.iloc[0]["low"] == 45
    assert result.iloc[0]["close"] == 50
    assert result.iloc[0]["raw_close"] == 100
    assert result.iloc[0]["split_adjusted_close"] == 100
    assert result.iloc[0]["total_return_index"] == 50


def test_yahoo_chart_rejects_absent_action_evidence():
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [1704153600],
                    "indicators": {
                        "quote": [
                            {
                                "open": [100],
                                "high": [110],
                                "low": [90],
                                "close": [100],
                                "volume": [1000],
                            }
                        ],
                        "adjclose": [{"adjclose": [50]}],
                    },
                }
            ]
        }
    }

    with pytest.raises(ValueError, match="action evidence"):
        normalize_yahoo_chart_payload(payload, ticker="PETR4", asset_class="BR_STOCK")


def test_yahoo_chart_rejects_missing_raw_ohlc():
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [1704153600],
                    "events": {},
                    "indicators": {
                        "quote": [
                            {
                                "open": [100],
                                "low": [90],
                                "close": [100],
                                "volume": [1000],
                            }
                        ],
                        "adjclose": [{"adjclose": [50]}],
                    },
                }
            ]
        }
    }

    with pytest.raises(ValueError, match="raw OHLC"):
        normalize_yahoo_chart_payload(payload, ticker="PETR4", asset_class="BR_STOCK")


def test_yahoo_chart_rejects_missing_volume():
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [1704153600],
                    "events": {},
                    "indicators": {
                        "quote": [
                            {
                                "open": [100],
                                "high": [110],
                                "low": [90],
                                "close": [100],
                            }
                        ],
                        "adjclose": [{"adjclose": [50]}],
                    },
                }
            ]
        }
    }

    with pytest.raises(ValueError, match="volume"):
        normalize_yahoo_chart_payload(payload, ticker="PETR4", asset_class="BR_STOCK")


def test_yahoo_chart_applies_splits_without_treating_dividends_as_price_return():
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [1704153600, 1704240000],
                    "events": {
                        "splits": {
                            "1704240000": {
                                "date": 1704240000,
                                "numerator": 2,
                                "denominator": 1,
                                "splitRatio": "2:1",
                            }
                        }
                    },
                    "indicators": {
                        "quote": [
                            {
                                "open": [100, 52],
                                "high": [102, 53],
                                "low": [99, 51],
                                "close": [100, 52],
                                "volume": [1000, 2200],
                            }
                        ],
                        "adjclose": [{"adjclose": [48, 52]}],
                    },
                }
            ]
        }
    }

    result = normalize_yahoo_chart_payload(payload, ticker="PETR4", asset_class="BR_STOCK")

    assert result["raw_close"].tolist() == [100.0, 52.0]
    assert result["split_adjusted_close"].tolist() == [50.0, 52.0]
    assert result["total_return_index"].tolist() == [48.0, 52.0]
    assert result["close"].tolist() == [48.0, 52.0]


def test_yahoo_chart_rejects_infinite_split_ratio():
    payload = {
        "chart": {
            "result": [
                {
                    "timestamp": [1704153600],
                    "events": {
                        "splits": {
                            "1704240000": {
                                "date": 1704240000,
                                "numerator": float("inf"),
                                "denominator": 1,
                                "splitRatio": "inf:1",
                            }
                        }
                    },
                    "indicators": {
                        "quote": [
                            {
                                "open": [100],
                                "high": [102],
                                "low": [99],
                                "close": [100],
                                "volume": [1000],
                            }
                        ],
                        "adjclose": [{"adjclose": [100]}],
                    },
                }
            ]
        }
    }

    with pytest.raises(ValueError, match="Malformed Yahoo split ratio"):
        normalize_yahoo_chart_payload(payload, ticker="PETR4", asset_class="BR_STOCK")


def test_public_source_adapters_parse_complete_cached_fixtures(tmp_path):
    calls = []

    def fixture_fetch(url: str) -> bytes:
        calls.append(url)
        return (FIXTURES / Path(url).name).read_bytes()

    b3 = B3PublicSourceAdapter(cache_dir=tmp_path, fetch_bytes=fixture_fetch)
    cvm = CVMPublicSourceAdapter(cache_dir=tmp_path, fetch_bytes=fixture_fetch)
    bcb = BCBPublicSourceAdapter(cache_dir=tmp_path, fetch_bytes=fixture_fetch)
    ibge = IBGEPublicSourceAdapter(cache_dir=tmp_path, fetch_bytes=fixture_fetch)

    market = b3.fetch("https://fixture.test/b3_market.csv", cache_key="b3")
    fundamentals = cvm.fetch("https://fixture.test/cvm_fundamentals.csv", cache_key="cvm")
    selic = bcb.fetch(
        "https://fixture.test/bcb_selic.json",
        cache_key="bcb",
        series="selic",
        available_at_by_reference={
            "2024-01-02": "2024-01-03T09:00:00",
            "2024-01-03": "2024-01-04T09:00:00",
        },
    )
    ipca = ibge.fetch(
        "https://fixture.test/ibge_ipca.json",
        cache_key="ibge",
        series="ipca",
        available_at_by_reference={"2024-01-01": "2024-02-08T09:00:00"},
    )
    cached_market = b3.fetch("https://fixture.test/b3_market.csv", cache_key="b3")

    assert market.loc[1, "total_return_index"] == pytest.approx(100.9162)
    assert fundamentals.loc[0, "reference_date"] == pd.Timestamp("2023-12-31")
    assert fundamentals.loc[0, "available_at"] == pd.Timestamp("2024-03-08T18:00:00")
    assert selic.loc[0, "selic"] == 11.75
    assert ipca.loc[0, "ipca"] == 0.42
    pd.testing.assert_frame_equal(cached_market, market)
    assert calls.count("https://fixture.test/b3_market.csv") == 1
    assert b3.provenance()["checksum"]
    assert b3.provenance()["retrieved_at"]
    assert b3.provenance()["license"] == "B3 market-data terms"


def test_public_source_adapter_fails_closed_on_incomplete_authoritative_history(tmp_path):
    adapter = B3PublicSourceAdapter(
        cache_dir=tmp_path,
        fetch_bytes=lambda _url: b"date;ticker;raw_close;volume\n2024-01-02;PETR4;38.2;1000\n",
    )

    with pytest.raises(SourceUnavailableError, match="total_return_index"):
        adapter.fetch("https://fixture.test/incomplete.csv", cache_key="incomplete")

    provenance = adapter.provenance()
    assert provenance["reconciliation_status"] == "unavailable"
    assert provenance["errors"]


def test_b3_adapter_rejects_duplicate_market_keys(tmp_path):
    payload = (
        "date;ticker;asset_class;raw_close;split_adjusted_close;total_return_index;volume\n"
        "2024-01-02;PETR4;BR_STOCK;38.2;38.2;100;1000\n"
        "2024-01-02;PETR4;BR_STOCK;38.3;38.3;101;1100\n"
    ).encode()
    adapter = B3PublicSourceAdapter(
        cache_dir=tmp_path, fetch_bytes=lambda _url: payload
    )

    with pytest.raises(SourceUnavailableError, match="duplicate"):
        adapter.fetch("https://fixture.test/b3-duplicate.csv", cache_key="b3-duplicate")


def test_cvm_adapter_rejects_missing_timestamp_and_infinite_numeric(tmp_path):
    payload = (
        "CD_CVM;DENOM_SOCIAL;DT_REFER;DT_RECEB;VL_PATRIM_LIQ\n"
        "9512;PETROBRAS;2023-12-31;;inf\n"
    ).encode()
    adapter = CVMPublicSourceAdapter(
        cache_dir=tmp_path, fetch_bytes=lambda _url: payload
    )

    with pytest.raises(SourceUnavailableError, match="invalid CVM"):
        adapter.fetch("https://fixture.test/cvm-malformed.csv", cache_key="cvm-malformed")


def test_bcb_adapter_rejects_non_finite_and_duplicate_series_records(tmp_path):
    payload = json.dumps(
        [
            {"data": "02/01/2024", "valor": "NaN"},
            {"data": "02/01/2024", "valor": "11.75"},
        ]
    ).encode()
    adapter = BCBPublicSourceAdapter(
        cache_dir=tmp_path, fetch_bytes=lambda _url: payload
    )

    with pytest.raises(SourceUnavailableError, match="invalid BCB"):
        adapter.fetch(
            "https://fixture.test/bcb-malformed.json",
            cache_key="bcb-malformed",
            series="selic",
            available_at_by_reference={"2024-01-02": "2024-01-03T09:00:00"},
        )


def test_ibge_adapter_rejects_missing_required_dimensions_and_infinite_value(tmp_path):
    payload = json.dumps(
        [{"D1C": "1", "D3C": "202401", "V": "Infinity"}]
    ).encode()
    adapter = IBGEPublicSourceAdapter(
        cache_dir=tmp_path, fetch_bytes=lambda _url: payload
    )

    with pytest.raises(SourceUnavailableError, match="invalid IBGE"):
        adapter.fetch(
            "https://fixture.test/ibge-malformed.json",
            cache_key="ibge-malformed",
            series="ipca",
            available_at_by_reference={"2024-01-01": "2024-02-08T09:00:00"},
        )


def test_b3_adapter_rejects_non_chronological_source_order(tmp_path):
    adapter = B3PublicSourceAdapter(
        cache_dir=tmp_path,
        fetch_bytes=lambda _url: (FIXTURES / "b3_market_descending.csv").read_bytes(),
    )

    with pytest.raises(SourceUnavailableError, match="non-chronological B3"):
        adapter.fetch("https://fixture.test/b3_market_descending.csv", cache_key="b3-order")


def test_cvm_adapter_rejects_non_chronological_source_order(tmp_path):
    adapter = CVMPublicSourceAdapter(
        cache_dir=tmp_path,
        fetch_bytes=lambda _url: (FIXTURES / "cvm_fundamentals_descending.csv").read_bytes(),
    )

    with pytest.raises(SourceUnavailableError, match="non-chronological CVM"):
        adapter.fetch(
            "https://fixture.test/cvm_fundamentals_descending.csv", cache_key="cvm-order"
        )


def test_bcb_adapter_rejects_non_chronological_source_order(tmp_path):
    adapter = BCBPublicSourceAdapter(
        cache_dir=tmp_path,
        fetch_bytes=lambda _url: (FIXTURES / "bcb_selic_descending.json").read_bytes(),
    )

    with pytest.raises(SourceUnavailableError, match="non-chronological BCB"):
        adapter.fetch(
            "https://fixture.test/bcb_selic_descending.json",
            cache_key="bcb-order",
            series="selic",
            available_at_by_reference={
                "2024-01-02": "2024-01-03T09:00:00",
                "2024-01-03": "2024-01-04T09:00:00",
            },
        )


def test_ibge_adapter_rejects_non_chronological_source_order(tmp_path):
    adapter = IBGEPublicSourceAdapter(
        cache_dir=tmp_path,
        fetch_bytes=lambda _url: (FIXTURES / "ibge_ipca_descending.json").read_bytes(),
    )

    with pytest.raises(SourceUnavailableError, match="non-chronological IBGE"):
        adapter.fetch(
            "https://fixture.test/ibge_ipca_descending.json",
            cache_key="ibge-order",
            series="ipca",
            available_at_by_reference={
                "2024-01-01": "2024-02-08T09:00:00",
                "2024-02-01": "2024-03-12T09:00:00",
            },
        )


def test_yahoo_fallback_is_rejected_when_overlap_does_not_reconcile():
    authoritative = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02"]),
            "ticker": ["PETR4"],
            "raw_close": [100.0],
            "split_adjusted_close": [100.0],
            "total_return_index": [100.0],
            "close": [100.0],
            "volume": [1000.0],
        }
    )
    yahoo = authoritative.copy()
    yahoo["total_return_index"] = 80.0
    yahoo["close"] = 80.0

    with pytest.raises(ReconciliationError, match="total_return_index"):
        reconcile_yahoo_fallback(authoritative, yahoo, max_relative_error=0.01)


def test_yahoo_fallback_records_audited_rows_and_reconciliation_status():
    authoritative = pd.DataFrame(
        {
            "date": pd.to_datetime(["2024-01-02"]),
            "ticker": ["PETR4"],
            "raw_close": [100.0],
            "split_adjusted_close": [100.0],
            "total_return_index": [99.0],
            "close": [99.0],
            "volume": [1000.0],
        }
    )
    yahoo = pd.concat(
        [
            authoritative,
            authoritative.assign(
                date=pd.Timestamp("2024-01-03"),
                raw_close=101.0,
                split_adjusted_close=101.0,
                total_return_index=100.0,
                close=100.0,
            ),
        ],
        ignore_index=True,
    )

    result, audit = reconcile_yahoo_fallback(authoritative, yahoo)

    assert result["data_source"].tolist() == ["authoritative", "yahoo_fallback"]
    assert audit["fallback_used"] is True
    assert audit["reconciliation_status"] == "reconciled"
    assert audit["fallback_rows"] == 1


def test_yahoo_provider_manifest_marks_unreconciled_fallback_explicitly():
    metadata = YahooDatasetProvider().source_metadata("2024-01-31T23:59:59+00:00")

    assert metadata["prices"]["source"] == "Yahoo Finance"
    assert metadata["prices"]["fallback_used"] is True
    assert metadata["prices"]["reconciliation_status"] == "unreconciled_fallback"
    assert metadata["prices"]["errors"] == [
        "authoritative B3 history was not supplied for reconciliation"
    ]
    assert {
        "source",
        "license",
        "retrieved_at",
        "checksum",
        "reconciliation_status",
        "fallback_used",
        "errors",
        "exclusions",
    }.issubset(metadata["prices"])


def test_yahoo_provider_records_each_unavailable_fallback_series(monkeypatch):
    monkeypatch.setenv("OPERUM_YAHOO_CHART_ONLY", "true")
    provider = YahooDatasetProvider()

    def fixture_chart(_symbol, *, ticker, asset_class, since, until):
        del since, until
        if ticker == "DEAD3":
            return pd.DataFrame()
        return pd.DataFrame(
            {
                "date": pd.to_datetime(["2024-01-02"]),
                "ticker": [ticker],
                "asset_class": [asset_class],
                "open": [10.0],
                "high": [10.1],
                "low": [9.9],
                "raw_close": [10.0],
                "split_adjusted_close": [10.0],
                "total_return_index": [10.0],
                "close": [10.0],
                "volume": [1000.0],
            }
        )

    monkeypatch.setattr(provider, "_fetch_chart_adjusted", fixture_chart)

    result = provider.fetch_market(
        [("LIVE3", "BR_STOCK"), ("DEAD3", "BR_STOCK")],
        since="2024-01-01",
        until="2024-01-04",
    )

    assert result["ticker"].tolist() == ["LIVE3"]
    assert provider.source_metadata("2024-01-04")["prices"]["exclusions"] == [
        {"ticker": "DEAD3", "reason": "yahoo_fallback_unavailable"}
    ]
