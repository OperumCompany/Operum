from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import re
from typing import Callable, Iterable, Protocol

import numpy as np
import pandas as pd
import requests
import yfinance as yf


CONTEXT_SYMBOLS = {
    "ibov_close": "^BVSP",
    "usdbrl_close": "BRL=X",
    "brent_close": "BZ=F",
}


class SourceUnavailableError(RuntimeError):
    """An authoritative public input cannot satisfy the point-in-time contract."""


class ReconciliationError(RuntimeError):
    """A fallback series disagrees with authoritative overlap."""


def _is_chronological(
    frame: pd.DataFrame, date_column: str, *, group_columns: tuple[str, ...] = ()
) -> bool:
    if not group_columns:
        return frame[date_column].is_monotonic_increasing
    return all(
        group[date_column].is_monotonic_increasing
        for _, group in frame.groupby(list(group_columns), sort=False)
    )


class PublicSourceAdapter(Protocol):
    def fetch(self, url: str, *, cache_key: str, **kwargs) -> pd.DataFrame: ...

    def provenance(self) -> dict: ...


def _frame_checksum(frame: pd.DataFrame) -> str:
    normalized = frame.sort_index(axis=1).sort_values(
        [column for column in ("ticker", "date", "reference_date") if column in frame]
    )
    return hashlib.sha256(
        pd.util.hash_pandas_object(normalized, index=False).values.tobytes()
    ).hexdigest()


@dataclass
class _CachedPublicSourceAdapter:
    cache_dir: str | Path
    fetch_bytes: Callable[[str], bytes] | None = None

    source: str = "public"
    license_name: str = "public-data terms"

    def __post_init__(self) -> None:
        self.cache_dir = Path(self.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._provenance: dict = {
            "source": self.source,
            "license": self.license_name,
            "retrieved_at": None,
            "checksum": None,
            "reconciliation_status": "not_run",
            "fallback_used": False,
            "errors": [],
            "exclusions": [],
        }

    def _download(self, url: str) -> bytes:
        if self.fetch_bytes is not None:
            return self.fetch_bytes(url)
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return response.content

    def _payload(self, url: str, cache_key: str) -> bytes:
        safe_key = re.sub(r"[^A-Za-z0-9_.-]+", "-", cache_key).strip("-") or "payload"
        payload_path = self.cache_dir / f"{self.source.lower()}-{safe_key}.cache"
        metadata_path = payload_path.with_suffix(".metadata.json")
        if payload_path.exists() and metadata_path.exists():
            payload = payload_path.read_bytes()
            self._provenance.update(json.loads(metadata_path.read_text(encoding="utf-8")))
            return payload
        try:
            payload = self._download(url)
        except Exception as exc:
            self._provenance["reconciliation_status"] = "unavailable"
            self._provenance["errors"] = [str(exc)]
            raise SourceUnavailableError(f"{self.source} endpoint unavailable: {exc}") from exc
        if not payload:
            self._provenance["reconciliation_status"] = "unavailable"
            self._provenance["errors"] = ["empty payload"]
            raise SourceUnavailableError(f"{self.source} returned an empty payload")
        self._provenance.update(
            {
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "checksum": hashlib.sha256(payload).hexdigest(),
            }
        )
        payload_path.write_bytes(payload)
        metadata_path.write_text(
            json.dumps(self._provenance, ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return payload

    def provenance(self) -> dict:
        return dict(self._provenance)

    def _parse_or_fail(self, parser: Callable[[], pd.DataFrame]) -> pd.DataFrame:
        try:
            frame = parser()
            if frame.empty:
                raise ValueError("empty authoritative history")
        except Exception as exc:
            self._provenance["reconciliation_status"] = "unavailable"
            self._provenance["errors"] = [str(exc)]
            raise SourceUnavailableError(f"{self.source} authoritative history malformed: {exc}") from exc
        self._provenance["reconciliation_status"] = "authoritative"
        self._provenance["parsed_checksum"] = _frame_checksum(frame)
        return frame


@dataclass
class B3PublicSourceAdapter(_CachedPublicSourceAdapter):
    source: str = "B3"
    license_name: str = "B3 market-data terms"

    def fetch(self, url: str, *, cache_key: str, **_kwargs) -> pd.DataFrame:
        payload = self._payload(url, cache_key)

        def parse() -> pd.DataFrame:
            frame = pd.read_csv(io.BytesIO(payload), sep=None, engine="python")
            required = {
                "date",
                "ticker",
                "asset_class",
                "raw_close",
                "split_adjusted_close",
                "total_return_index",
                "volume",
            }
            missing = required.difference(frame.columns)
            if missing:
                raise ValueError(f"missing canonical fields: {sorted(missing)}")
            frame = frame.copy()
            frame["date"] = pd.to_datetime(frame["date"], errors="raise")
            for column in (
                "raw_close",
                "split_adjusted_close",
                "total_return_index",
                "volume",
            ):
                frame[column] = pd.to_numeric(frame[column], errors="raise")
            invalid = ~np.isfinite(
                frame[["raw_close", "split_adjusted_close", "total_return_index", "volume"]]
            ) | (
                frame[["raw_close", "split_adjusted_close", "total_return_index", "volume"]]
                <= 0
            )
            if invalid.any().any():
                raise ValueError("non-positive or non-finite market values")
            if frame["date"].isna().any():
                raise ValueError("invalid B3 dates")
            if frame[["ticker", "asset_class"]].isna().any().any():
                raise ValueError("invalid B3 identifiers")
            if frame["ticker"].astype(str).str.strip().eq("").any():
                raise ValueError("invalid B3 ticker")
            if not frame["asset_class"].isin({"BR_STOCK", "FII"}).all():
                raise ValueError("invalid B3 asset_class")
            if frame.duplicated(["ticker", "date"]).any():
                raise ValueError("duplicate B3 market key")
            if not _is_chronological(frame, "date", group_columns=("ticker",)):
                raise ValueError("non-chronological B3 source order")
            frame["close"] = frame["total_return_index"]
            return frame.sort_values(["ticker", "date"]).reset_index(drop=True)

        return self._parse_or_fail(parse)


@dataclass
class CVMPublicSourceAdapter(_CachedPublicSourceAdapter):
    source: str = "CVM"
    license_name: str = "Dados Abertos CVM"

    def fetch(self, url: str, *, cache_key: str, **_kwargs) -> pd.DataFrame:
        payload = self._payload(url, cache_key)

        def parse() -> pd.DataFrame:
            raw = pd.read_csv(io.BytesIO(payload), sep=";", encoding="utf-8-sig")
            required = {"CD_CVM", "DENOM_SOCIAL", "DT_REFER", "DT_RECEB", "VL_PATRIM_LIQ"}
            missing = required.difference(raw.columns)
            if missing:
                raise ValueError(f"missing CVM fields: {sorted(missing)}")
            frame = pd.DataFrame(
                {
                    "reference_date": pd.to_datetime(raw["DT_REFER"], errors="raise"),
                    "available_at": pd.to_datetime(raw["DT_RECEB"], errors="raise"),
                    "cvm_code": raw["CD_CVM"].astype(str),
                    "company_name": raw["DENOM_SOCIAL"].astype(str),
                    "net_equity": pd.to_numeric(raw["VL_PATRIM_LIQ"], errors="raise"),
                }
            )
            invalid_dates = frame[["reference_date", "available_at"]].isna().any().any()
            invalid_numeric = (~np.isfinite(frame[["net_equity"]])).any().any()
            invalid_identifiers = (
                raw[["CD_CVM", "DENOM_SOCIAL"]].isna().any().any()
                or frame["cvm_code"].str.strip().eq("").any()
                or frame["company_name"].str.strip().eq("").any()
            )
            if (
                invalid_dates
                or invalid_numeric
                or invalid_identifiers
                or (frame["reference_date"] > frame["available_at"]).any()
            ):
                raise ValueError("invalid CVM point-in-time record")
            if frame.duplicated(["cvm_code", "reference_date", "available_at"]).any():
                raise ValueError("duplicate CVM point-in-time record")
            if not _is_chronological(
                frame, "available_at", group_columns=("cvm_code",)
            ):
                raise ValueError("non-chronological CVM source order")
            return frame.sort_values(["available_at", "cvm_code"]).reset_index(drop=True)

        return self._parse_or_fail(parse)


def _availability_timestamp(
    reference_date: pd.Timestamp, available_at_by_reference: dict[str, str]
) -> pd.Timestamp:
    key = reference_date.strftime("%Y-%m-%d")
    if key not in available_at_by_reference:
        raise ValueError(f"authoritative available_at missing for {key}")
    available_at = pd.Timestamp(available_at_by_reference[key])
    if available_at < reference_date:
        raise ValueError(f"available_at precedes reference_date for {key}")
    return available_at


@dataclass
class BCBPublicSourceAdapter(_CachedPublicSourceAdapter):
    source: str = "BCB"
    license_name: str = "Licenca de Dados Abertos BCB"

    def fetch(
        self,
        url: str,
        *,
        cache_key: str,
        series: str,
        available_at_by_reference: dict[str, str],
    ) -> pd.DataFrame:
        payload = self._payload(url, cache_key)

        def parse() -> pd.DataFrame:
            records = json.loads(payload.decode("utf-8-sig"))
            if not isinstance(records, list) or not str(series).strip():
                raise ValueError("invalid BCB payload or series")
            rows = []
            for record in records:
                if not isinstance(record, dict) or not {"data", "valor"}.issubset(record):
                    raise ValueError("invalid BCB required fields")
                reference_date = pd.to_datetime(record["data"], dayfirst=True, errors="raise")
                rows.append(
                    {
                        "reference_date": reference_date,
                        "available_at": _availability_timestamp(
                            reference_date, available_at_by_reference
                        ),
                        series: float(str(record["valor"]).replace(",", ".")),
                    }
                )
            frame = pd.DataFrame(rows)
            if (
                frame[["reference_date", "available_at"]].isna().any().any()
                or (~np.isfinite(frame[[series]])).any().any()
                or frame.duplicated(["reference_date"]).any()
            ):
                raise ValueError("invalid BCB point-in-time records")
            if not _is_chronological(frame, "reference_date"):
                raise ValueError("non-chronological BCB source order")
            return frame.sort_values("reference_date").reset_index(drop=True)

        return self._parse_or_fail(parse)


@dataclass
class IBGEPublicSourceAdapter(_CachedPublicSourceAdapter):
    source: str = "IBGE"
    license_name: str = "Dados publicos SIDRA/IBGE"

    def fetch(
        self,
        url: str,
        *,
        cache_key: str,
        series: str,
        available_at_by_reference: dict[str, str],
    ) -> pd.DataFrame:
        payload = self._payload(url, cache_key)

        def parse() -> pd.DataFrame:
            records = json.loads(payload.decode("utf-8-sig"))
            if not isinstance(records, list) or not str(series).strip():
                raise ValueError("invalid IBGE payload or series")
            rows = []
            for record in records:
                if not isinstance(record, dict) or not {
                    "D1C", "D2C", "D3C", "V"
                }.issubset(record):
                    raise ValueError("invalid IBGE required fields")
                reference_date = pd.to_datetime(str(record["D3C"]), format="%Y%m", errors="raise")
                rows.append(
                    {
                        "reference_date": reference_date,
                        "available_at": _availability_timestamp(
                            reference_date, available_at_by_reference
                        ),
                        series: float(str(record["V"]).replace(",", ".")),
                    }
                )
            frame = pd.DataFrame(rows)
            if (
                frame[["reference_date", "available_at"]].isna().any().any()
                or (~np.isfinite(frame[[series]])).any().any()
                or frame.duplicated(["reference_date"]).any()
            ):
                raise ValueError("invalid IBGE point-in-time records")
            if not _is_chronological(frame, "reference_date"):
                raise ValueError("non-chronological IBGE source order")
            return frame.sort_values("reference_date").reset_index(drop=True)

        return self._parse_or_fail(parse)


def reconcile_yahoo_fallback(
    authoritative: pd.DataFrame,
    yahoo: pd.DataFrame,
    *,
    max_relative_error: float = 0.02,
) -> tuple[pd.DataFrame, dict]:
    """Use Yahoo rows only after canonical overlap reconciles with public history."""
    canonical = {"date", "ticker", "raw_close", "split_adjusted_close", "total_return_index"}
    for name, frame in (("authoritative", authoritative), ("Yahoo", yahoo)):
        missing = canonical.difference(frame.columns)
        if missing or frame.empty:
            raise ReconciliationError(f"{name} history cannot be reconciled: {sorted(missing)}")
    primary = authoritative.copy()
    fallback = yahoo.copy()
    primary["date"] = pd.to_datetime(primary["date"]).dt.tz_localize(None)
    fallback["date"] = pd.to_datetime(fallback["date"]).dt.tz_localize(None)
    overlap = primary.merge(fallback, on=["date", "ticker"], suffixes=("_primary", "_yahoo"))
    if overlap.empty:
        raise ReconciliationError("Yahoo fallback has no authoritative overlap")
    compared = []
    for column in ("raw_close", "split_adjusted_close", "total_return_index"):
        left = pd.to_numeric(overlap[f"{column}_primary"], errors="coerce")
        right = pd.to_numeric(overlap[f"{column}_yahoo"], errors="coerce")
        denominator = left.abs().replace(0, np.nan)
        errors = (right - left).abs() / denominator
        if errors.isna().any() or (~np.isfinite(errors)).any() or (errors > max_relative_error).any():
            raise ReconciliationError(f"Yahoo fallback failed reconciliation for {column}")
        compared.extend(errors.tolist())
    keys = primary[["date", "ticker"]].drop_duplicates()
    missing_rows = fallback.merge(keys, on=["date", "ticker"], how="left", indicator=True)
    missing_rows = missing_rows.loc[missing_rows["_merge"] == "left_only"].drop(columns="_merge")
    primary["data_source"] = "authoritative"
    missing_rows["data_source"] = "yahoo_fallback"
    combined = pd.concat([primary, missing_rows], ignore_index=True, sort=False).sort_values(
        ["ticker", "date"]
    ).reset_index(drop=True)
    audit = {
        "fallback_used": not missing_rows.empty,
        "reconciliation_status": "reconciled",
        "overlap_rows": len(overlap),
        "fallback_rows": len(missing_rows),
        "max_relative_error": max(compared, default=0.0),
        "authoritative_checksum": _frame_checksum(primary.drop(columns="data_source")),
        "fallback_checksum": _frame_checksum(fallback),
    }
    return combined, audit


def _single_symbol_frame(raw: pd.DataFrame, symbol: str | None = None) -> pd.DataFrame:
    frame = raw.copy()
    if not isinstance(frame.columns, pd.MultiIndex):
        return frame

    for level in range(frame.columns.nlevels):
        values = {str(value) for value in frame.columns.get_level_values(level)}
        if symbol and symbol in values:
            return frame.xs(symbol, axis=1, level=level, drop_level=True)

    for level in reversed(range(frame.columns.nlevels)):
        if len(frame.columns.get_level_values(level).unique()) == 1:
            return frame.droplevel(level, axis=1)
    raise ValueError("Histórico do Yahoo contém mais de um ticker sem seleção explícita")


def normalize_yfinance_history(
    raw: pd.DataFrame,
    *,
    ticker: str,
    asset_class: str,
    yahoo_symbol: str | None = None,
) -> pd.DataFrame:
    frame = _single_symbol_frame(raw, yahoo_symbol)
    rename = {str(column).lower().replace(" ", "_"): column for column in frame.columns}
    required = {
        "open", "high", "low", "close", "adj_close", "volume", "stock_splits", "dividends"
    }
    missing = required.difference(rename)
    if missing:
        raise ValueError(
            f"Yahoo adjusted/action evidence incomplete for {ticker}: {sorted(missing)}"
        )

    raw_close = pd.to_numeric(frame[rename["close"]], errors="coerce")
    total_return_index = pd.to_numeric(frame[rename["adj_close"]], errors="coerce")
    split_events = pd.to_numeric(frame[rename["stock_splits"]], errors="coerce")
    dividends = pd.to_numeric(frame[rename["dividends"]], errors="coerce")
    if split_events.isna().any() or dividends.isna().any():
        raise ValueError(f"Yahoo action evidence malformed for {ticker}")
    split_factor = (
        split_events.replace(0, 1.0)
        .shift(-1, fill_value=1.0)
        .iloc[::-1]
        .cumprod()
        .iloc[::-1]
    )
    split_adjusted_close = raw_close / split_factor
    total_adjustment = total_return_index / raw_close.replace(0, np.nan)

    normalized = pd.DataFrame(
        {
            "date": pd.to_datetime(frame.index, utc=True).tz_localize(None),
            "ticker": ticker.upper().replace(".SA", ""),
            "asset_class": asset_class,
            "open": (
                pd.to_numeric(frame[rename["open"]], errors="coerce") * total_adjustment
            ).to_numpy(),
            "high": (
                pd.to_numeric(frame[rename["high"]], errors="coerce") * total_adjustment
            ).to_numpy(),
            "low": (
                pd.to_numeric(frame[rename["low"]], errors="coerce") * total_adjustment
            ).to_numpy(),
            "raw_close": raw_close.to_numpy(),
            "split_adjusted_close": split_adjusted_close.to_numpy(),
            "total_return_index": total_return_index.to_numpy(),
            "close": total_return_index.to_numpy(),
            "volume": pd.to_numeric(frame[rename["volume"]], errors="coerce").to_numpy(),
        }
    )
    return normalized.dropna(subset=["date", "close", "volume"]).reset_index(drop=True)


def normalize_yahoo_chart_payload(
    payload: dict,
    *,
    ticker: str,
    asset_class: str,
) -> pd.DataFrame:
    results = payload.get("chart", {}).get("result") or []
    if not results:
        return pd.DataFrame(
            columns=[
                "date", "ticker", "asset_class", "open", "high", "low", "raw_close",
                "split_adjusted_close", "total_return_index", "close", "volume",
            ]
        )
    result = results[0]
    if "events" not in result or not isinstance(result["events"], dict):
        raise ValueError(f"Yahoo action evidence incomplete for {ticker}")
    events = result["events"]
    timestamps = result.get("timestamp") or []
    quotes = result.get("indicators", {}).get("quote") or []
    adjusted_sets = result.get("indicators", {}).get("adjclose") or []
    if not timestamps or not quotes or not adjusted_sets:
        raise ValueError(f"Yahoo canonical price evidence incomplete for {ticker}")
    quote = quotes[0]
    adjusted = adjusted_sets[0].get("adjclose") or []
    if not isinstance(quote, dict):
        raise ValueError(f"Yahoo raw OHLC evidence incomplete for {ticker}")
    required_quote_columns = ("open", "high", "low", "close")
    for column in required_quote_columns:
        values = quote.get(column)
        if not isinstance(values, list) or len(values) != len(timestamps):
            raise ValueError(f"Yahoo raw OHLC evidence incomplete for {ticker}")
    volumes = quote.get("volume")
    if not isinstance(volumes, list) or len(volumes) != len(timestamps):
        raise ValueError(f"Yahoo volume evidence incomplete for {ticker}")
    if len(adjusted) != len(timestamps):
        raise ValueError(f"Yahoo adjusted-close evidence incomplete for {ticker}")

    split_events = events.get("splits", {})
    dividend_events = events.get("dividends", {})
    if not isinstance(split_events, dict) or not isinstance(dividend_events, dict):
        raise ValueError(f"Yahoo action evidence malformed for {ticker}")
    splits: list[tuple[int, float]] = []
    for event in split_events.values():
        if not isinstance(event, dict):
            raise ValueError(f"Malformed Yahoo split event for {ticker}")
        split_date = event.get("date")
        numerator = event.get("numerator")
        denominator = event.get("denominator")
        if split_date is None or numerator is None or denominator in (None, 0):
            raise ValueError(f"Malformed Yahoo split event for {ticker}")
        ratio = float(numerator) / float(denominator)
        if not np.isfinite(ratio) or ratio <= 0:
            raise ValueError(f"Malformed Yahoo split ratio for {ticker}")
        splits.append((int(split_date), ratio))
    for event in dividend_events.values():
        if not isinstance(event, dict) or event.get("date") is None:
            raise ValueError(f"Malformed Yahoo dividend event for {ticker}")
        try:
            amount = float(event["amount"])
            event_date = int(event["date"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"Malformed Yahoo dividend event for {ticker}") from exc
        if not np.isfinite(amount) or amount < 0 or event_date <= 0:
            raise ValueError(f"Malformed Yahoo dividend event for {ticker}")

    rows = []
    for index, timestamp in enumerate(timestamps):
        try:
            timestamp_value = int(timestamp)
            raw_values = {
                column: float(quote[column][index]) for column in required_quote_columns
            }
            adjusted_close = float(adjusted[index])
            volume = float(volumes[index])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Yahoo canonical row malformed for {ticker}") from exc
        if not all(np.isfinite(value) and value > 0 for value in raw_values.values()):
            raise ValueError(f"Yahoo raw OHLC evidence malformed for {ticker}")
        if not np.isfinite(adjusted_close) or adjusted_close <= 0:
            raise ValueError(f"Yahoo adjusted-close evidence malformed for {ticker}")
        if not np.isfinite(volume) or volume < 0:
            raise ValueError(f"Yahoo volume evidence malformed for {ticker}")
        raw_close = raw_values["close"]
        ratio = adjusted_close / raw_close
        split_factor = 1.0
        for split_date, split_ratio in splits:
            if timestamp_value < split_date:
                split_factor *= split_ratio
        split_adjusted_close = raw_close / split_factor
        if not np.isfinite(split_adjusted_close) or split_adjusted_close <= 0:
            raise ValueError(f"Malformed Yahoo split-adjusted close for {ticker}")
        rows.append(
            {
                "date": pd.Timestamp(timestamp_value, unit="s", tz="UTC").tz_localize(None),
                "ticker": ticker.upper().replace(".SA", ""),
                "asset_class": asset_class,
                "open": raw_values["open"] * ratio,
                "high": raw_values["high"] * ratio,
                "low": raw_values["low"] * ratio,
                "raw_close": float(raw_close),
                "split_adjusted_close": split_adjusted_close,
                "total_return_index": float(adjusted_close),
                "close": float(adjusted_close),
                "volume": volume,
            }
        )
    return pd.DataFrame(
        rows,
        columns=[
            "date",
            "ticker",
            "asset_class",
            "open",
            "high",
            "low",
            "raw_close",
            "split_adjusted_close",
            "total_return_index",
            "close",
            "volume",
        ],
    )


def _b3_symbol(ticker: str) -> str:
    normalized = ticker.upper()
    return normalized if normalized.endswith(".SA") else f"{normalized}.SA"


@dataclass
class YahooDatasetProvider:
    """Downloads split/dividend-adjusted inputs for reproducible dataset builds."""

    timeout: int = 30
    _market_exclusions: list[dict] = field(default_factory=list, init=False, repr=False)
    _market_errors: list[str] = field(default_factory=list, init=False, repr=False)
    _market_checksum: str | None = field(default=None, init=False, repr=False)

    def _fetch_chart_adjusted(
        self,
        symbol: str,
        *,
        ticker: str,
        asset_class: str,
        since: str,
        until: str | None,
    ) -> pd.DataFrame:
        start = pd.Timestamp(since)
        start = start.tz_localize("UTC") if start.tzinfo is None else start.tz_convert("UTC")
        end = pd.Timestamp(until) if until else pd.Timestamp.now(tz="UTC")
        end = end.tz_localize("UTC") if end.tzinfo is None else end.tz_convert("UTC")
        period1 = int(start.timestamp())
        period2 = int(end.timestamp())
        response = requests.get(
            f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            params={
                "period1": period1,
                "period2": period2,
                "interval": "1d",
                "events": "div,splits",
                "includeAdjustedClose": "true",
            },
            headers={"User-Agent": "Mozilla/5.0 Operum/1.0"},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return normalize_yahoo_chart_payload(
            response.json(), ticker=ticker, asset_class=asset_class
        )

    def fetch_market(
        self,
        assets: Iterable[tuple[str, str]],
        *,
        since: str = "2019-01-01",
        until: str | None = None,
    ) -> pd.DataFrame:
        self._market_exclusions = []
        self._market_errors = []
        self._market_checksum = None
        asset_list = list(assets)
        symbols = [_b3_symbol(ticker) for ticker, _ in asset_list]
        raw = pd.DataFrame()
        if os.environ.get("OPERUM_YAHOO_CHART_ONLY", "false").lower() != "true":
            raw = yf.download(
                symbols,
                start=since,
                end=until,
                auto_adjust=False,
                actions=True,
                progress=False,
                timeout=self.timeout,
                group_by="ticker",
                threads=True,
            )
        parts: list[pd.DataFrame] = []
        for (ticker, asset_class), symbol in zip(asset_list, symbols, strict=True):
            if raw.empty:
                normalized = pd.DataFrame()
            else:
                try:
                    normalized = normalize_yfinance_history(
                        raw,
                        ticker=ticker,
                        asset_class=asset_class,
                        yahoo_symbol=symbol,
                    )
                except ValueError:
                    normalized = pd.DataFrame()
            if normalized.empty:
                try:
                    normalized = self._fetch_chart_adjusted(
                        symbol,
                        ticker=ticker,
                        asset_class=asset_class,
                        since=since,
                        until=until,
                    )
                except Exception as exc:
                    self._market_errors.append(f"{ticker}: {exc}")
                    normalized = pd.DataFrame()
            if not normalized.empty:
                parts.append(normalized)
            else:
                self._market_exclusions.append(
                    {"ticker": ticker, "reason": "yahoo_fallback_unavailable"}
                )
        if not parts:
            raise RuntimeError("Nenhum histórico ajustado foi obtido do Yahoo Finance")
        combined = pd.concat(parts, ignore_index=True)
        self._market_checksum = _frame_checksum(combined)
        return combined

    def fetch_context(
        self,
        *,
        since: str = "2019-01-01",
        until: str | None = None,
    ) -> pd.DataFrame:
        parts: list[pd.DataFrame] = []
        for column, symbol in CONTEXT_SYMBOLS.items():
            raw = pd.DataFrame()
            if os.environ.get("OPERUM_YAHOO_CHART_ONLY", "false").lower() != "true":
                raw = yf.download(
                    symbol,
                    start=since,
                    end=until,
                    auto_adjust=True,
                    actions=False,
                    progress=False,
                    timeout=self.timeout,
                )
            context_part = pd.DataFrame()
            if not raw.empty:
                frame = _single_symbol_frame(raw, symbol)
                close_column = next((item for item in frame.columns if str(item).lower() == "close"), None)
                if close_column is not None:
                    reference_dates = pd.to_datetime(
                        frame.index, utc=True
                    ).tz_localize(None)
                    context_part = pd.DataFrame(
                        {
                            "reference_date": reference_dates,
                            "available_at": reference_dates.normalize()
                            + pd.Timedelta(days=1)
                            - pd.Timedelta(nanoseconds=1),
                            column: pd.to_numeric(frame[close_column], errors="coerce").to_numpy(),
                        }
                    ).dropna()
            if context_part.empty:
                fallback = self._fetch_chart_adjusted(
                    symbol,
                    ticker=column,
                    asset_class="CONTEXT",
                    since=since,
                    until=until,
                )
                context_part = fallback[["date", "close"]].rename(
                    columns={"date": "reference_date", "close": column}
                )
                context_part["available_at"] = (
                    context_part["reference_date"].dt.normalize()
                    + pd.Timedelta(days=1)
                    - pd.Timedelta(nanoseconds=1)
                )
            if context_part.empty:
                raise RuntimeError(f"Contexto externo indisponível: {symbol}")
            parts.append(context_part)
        context = parts[0]
        for part in parts[1:]:
            context = pd.merge(
                context,
                part,
                on=["reference_date", "available_at"],
                how="outer",
            )
        return context.sort_values("reference_date").ffill().dropna().reset_index(drop=True)

    def source_metadata(self, cutoff: str | date) -> dict[str, dict]:
        def record(
            source: str,
            *,
            fallback: bool,
            error: str | None = None,
            checksum: str | None = None,
            exclusions: list[dict] | None = None,
            include_market_errors: bool = False,
        ) -> dict:
            return {
                "source": source,
                "license": "Yahoo Finance terms of service",
                "retrieved_at": str(cutoff),
                "checksum": checksum
                or "unavailable: runtime payload checksum not retained by legacy provider",
                "reconciliation_status": "unreconciled_fallback" if fallback else "unverified",
                "fallback_used": fallback,
                "errors": ([error] if error else [])
                + (self._market_errors if include_market_errors else []),
                "exclusions": list(exclusions or []),
            }

        return {
            "prices": record(
                "Yahoo Finance",
                fallback=True,
                error="authoritative B3 history was not supplied for reconciliation",
                checksum=self._market_checksum,
                exclusions=self._market_exclusions,
                include_market_errors=True,
            ),
            "benchmark": record("Yahoo Finance ^BVSP", fallback=False),
            "fx": record("Yahoo Finance BRL=X", fallback=False),
            "oil": record("Yahoo Finance BZ=F", fallback=False),
        }
