from __future__ import annotations

from collections.abc import Iterable
from copy import deepcopy
from numbers import Real
import re
from unicodedata import normalize as normalize_unicode
from urllib.parse import quote, unquote

import numpy as np
import pandas as pd


PIPELINE_SCHEMA_VERSION = "operum-fold-feature-pipeline-v1"
FEATURE_GROUP_SCHEMA_VERSION = "operum-feature-groups-v1"
DRIFT_SCHEMA_VERSION = "operum-feature-drift-v1"
UNKNOWN_CATEGORY = "__unknown__"

CATEGORICAL_FEATURES = ("sector", "subsector", "asset_subtype")
_CATEGORICAL_FEATURE_ALLOWLIST = frozenset(CATEGORICAL_FEATURES)
_FORBIDDEN_NAME_TOKENS = frozenset(
    {
        "ticker",
        "symbol",
        "assetid",
        "target",
        "label",
        "truth",
        "actual",
        "realized",
        "future",
        "forward",
        "predicted",
        "prediction",
        "outcome",
        "probability",
        "interval",
    }
)
_FORBIDDEN_FEATURE_NAMES = frozenset(
    {
        "ticker",
        "symbol",
        "asset_id",
        "cvm_code",
        "company_name",
        "target",
        "label",
        "outcome",
        "prediction",
        "truth",
        "baseline_prediction",
        "actual_return",
        "predicted_return",
        "lower_return",
        "upper_return",
        "interval_low",
        "interval_high",
        "probability_up",
        "direction_label",
        "initial_price",
        "actual_price",
        "horizon_days",
        "target_date",
        "scored_at",
    }
)
_FORBIDDEN_TOKEN_PAIRS = frozenset(
    {("asset", "id"), ("cvm", "code"), ("company", "name")}
)
_FORBIDDEN_COLLAPSED_MARKERS = _FORBIDDEN_NAME_TOKENS | frozenset(
    "".join(pair) for pair in _FORBIDDEN_TOKEN_PAIRS
)
_FORBIDDEN_COLLAPSED_FEATURE_NAMES = frozenset(
    "".join(character for character in name.casefold() if character.isalnum())
    for name in _FORBIDDEN_FEATURE_NAMES
)
_PIPELINE_STATE_KEYS = frozenset(
    {
        "schema_version",
        "numeric_feature_schema_version",
        "asset_classes",
        "numeric_features",
        "rank_features",
        "categorical_features",
        "winsor_limits",
        "numeric_medians",
        "category_vocabulary",
        "reference_numeric",
        "reference_category",
        "feature_columns",
    }
)
_NUMERIC_DRIFT_STAT_KEYS = frozenset({"mean", "std", "missing_rate"})
_CATEGORICAL_DRIFT_STAT_KEYS = frozenset({"missing_rate"})

FEATURE_GROUPS: dict[str, tuple[str, ...]] = {
    "price_momentum": (
        "return_1",
        "return_5",
        "return_21",
        "return_63",
        "price_to_sma_5",
        "price_to_sma_21",
        "price_to_sma_63",
        "rsi_14",
        "macd_normalized",
    ),
    "volatility_risk": (
        "volatility_5",
        "volatility_21",
        "volatility_63",
        "atr_14_normalized",
        "drawdown_63",
        "beta_63",
        "correlation_63",
    ),
    "liquidity": (
        "volume_zscore_21",
        "liquidity_21",
        "research_median_traded_value",
        "research_coverage",
        "research_liquidity_rank",
    ),
    "market_relative": (
        "benchmark_return_1",
        "benchmark_return_21",
        "benchmark_return_63",
        "relative_return_21",
    ),
    "macro_context": (
        "usdbrl_return_1",
        "usdbrl_return_21",
        "usdbrl_return_63",
        "brent_return_1",
        "brent_return_21",
        "brent_return_63",
        "selic",
        "cdi_rate",
        "cdi",
        "ipca_12m",
        "ipca",
    ),
    "fii_ifix_relative": (
        "ifix_return_1",
        "ifix_return_21",
        "ifix_return_63",
        "relative_return_ifix_1",
        "relative_return_ifix_21",
        "relative_return_ifix_63",
    ),
    "fii_macro_spreads": (
        "real_rate",
        "dividend_yield_spread_cdi",
        "credit_spread",
    ),
    "fii_income_value": (
        "dividend_yield",
        "p_vp",
        "distribution_stability",
    ),
    "fii_property_risk": (
        "vacancy_rate",
        "physical_vacancy",
        "financial_vacancy",
        "tenant_concentration",
        "top_tenant_share",
        "property_concentration",
        "top_property_share",
        "contract_duration",
        "weighted_average_lease_term",
        "contract_inflation_index",
        "ipca_indexed_share",
        "igpm_indexed_share",
        "emissions",
        "issuance_growth",
        "amortization",
        "amortization_yield",
    ),
    "equity_style": (
        "market_cap",
        "net_equity",
        "total_assets",
        "book_to_market",
        "p_e",
        "p_b",
        "ev_ebitda",
        "earnings_yield",
        "roe",
        "roa",
        "roic",
    ),
    "equity_fundamentals": (
        "gross_margin",
        "operating_margin",
        "net_margin",
        "revenue",
        "net_income",
        "net_debt",
        "ebitda",
        "net_debt_to_ebitda",
        "debt_to_equity",
        "current_ratio",
        "operating_cash_flow",
        "free_cash_flow",
        "cashflow_to_net_income",
        "earnings_surprise",
        "revenue_surprise",
    ),
    "equity_exposures": (
        "fx_exposure",
        "commodity_exposure",
        "rate_exposure",
        "usd_exposure",
        "oil_exposure",
        "interest_rate_exposure",
    ),
}

DEFAULT_RANK_FEATURES = (
    "return_21",
    "return_63",
    "volatility_21",
    "liquidity_21",
    "market_cap",
    "book_to_market",
    "earnings_yield",
    "roe",
    "dividend_yield",
    "p_vp",
)

_FII_GROUPS = {
    "fii_ifix_relative",
    "fii_macro_spreads",
    "fii_income_value",
    "fii_property_risk",
}
_EQUITY_GROUPS = {"equity_style", "equity_fundamentals", "equity_exposures"}
NUMERIC_FEATURE_SCHEMA_VERSION = "operum-numeric-features-v1"
NUMERIC_FEATURE_ALLOWLIST = frozenset(
    feature for features in FEATURE_GROUPS.values() for feature in features
)


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(values))


def _category_column(feature: str, category: str) -> str:
    encoded = UNKNOWN_CATEGORY if category == UNKNOWN_CATEGORY else quote(category, safe="")
    return f"category__{feature}__{encoded}"


def _normalized_name_tokens(value: str) -> tuple[str, ...]:
    decoded = normalize_unicode("NFKC", unquote(value.strip()))
    separated = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", decoded)
    separated = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", separated)
    separated = re.sub(r"(?<=[A-Za-z])(?=[0-9])", "_", separated)
    separated = re.sub(r"(?<=[0-9])(?=[A-Za-z])", "_", separated)
    return tuple(token.lower() for token in re.findall(r"[A-Za-z0-9]+", separated))


def _collapsed_name_semantics(value: str) -> str:
    normalized = normalize_unicode("NFKC", unquote(value.strip())).casefold()
    return "".join(character for character in normalized if character.isalnum())


def _has_forbidden_name_semantics(value: str) -> bool:
    collapsed = _collapsed_name_semantics(value)
    if any(marker in collapsed for marker in _FORBIDDEN_COLLAPSED_MARKERS):
        return True
    if collapsed in _FORBIDDEN_COLLAPSED_FEATURE_NAMES:
        return True
    tokens = _normalized_name_tokens(value)
    if set(tokens).intersection(_FORBIDDEN_NAME_TOKENS):
        return True
    if any(pair in _FORBIDDEN_TOKEN_PAIRS for pair in zip(tokens, tokens[1:])):
        return True
    return "_".join(tokens) in _FORBIDDEN_FEATURE_NAMES


def _validate_feature_names(features: Iterable[str], *, context: str) -> tuple[str, ...]:
    validated = tuple(features)
    for feature in validated:
        if not isinstance(feature, str) or not feature.strip():
            raise ValueError(f"Feature proibida em {context}: {feature!r}")
        if _has_forbidden_name_semantics(feature):
            raise ValueError(f"Feature proibida em {context}: {feature}")
    return validated


def _validate_raw_numeric_features(
    features: Iterable[str], *, context: str
) -> tuple[str, ...]:
    validated = _validate_feature_names(features, context=context)
    for feature in validated:
        if feature not in NUMERIC_FEATURE_ALLOWLIST:
            raise ValueError(
                f"Feature numerica fora de {NUMERIC_FEATURE_SCHEMA_VERSION}: {feature}"
            )
    return validated


def _validate_categorical_features(features: Iterable[str]) -> tuple[str, ...]:
    validated = _validate_feature_names(features, context="categorical_features")
    invalid = sorted(set(validated).difference(_CATEGORICAL_FEATURE_ALLOWLIST))
    if invalid:
        raise ValueError(f"Feature categorica proibida: {invalid[0]}")
    if len(validated) != len(set(validated)):
        raise ValueError("Estado de categorias inconsistente: colunas duplicadas")
    return validated


def _validate_nested_names(value, *, context: str = "state") -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise ValueError(f"Estado de feature pipeline inconsistente em {context}")
            _validate_feature_names((key,), context=context)
            _validate_nested_names(nested, context=f"{context}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, nested in enumerate(value):
            _validate_nested_names(nested, context=f"{context}[{index}]")
    elif isinstance(value, str):
        _validate_feature_names((value,), context=context)


def _is_finite_or_none(value) -> bool:
    return value is None or (
        isinstance(value, Real)
        and not isinstance(value, bool)
        and bool(np.isfinite(float(value)))
    )


def _validate_serialized_state(state: dict) -> None:
    if not isinstance(state, dict):
        raise ValueError("Estado de feature pipeline inconsistente")
    _validate_nested_names(state)
    if set(state) != _PIPELINE_STATE_KEYS:
        raise ValueError("Estado de feature pipeline inconsistente")
    if state["schema_version"] != PIPELINE_SCHEMA_VERSION:
        raise ValueError("Versao de feature pipeline incompatível")
    if state["numeric_feature_schema_version"] != NUMERIC_FEATURE_SCHEMA_VERSION:
        raise ValueError("Versao de features numericas incompatível")

    list_fields = (
        "asset_classes",
        "numeric_features",
        "rank_features",
        "categorical_features",
        "feature_columns",
    )
    if any(not isinstance(state[field], list) for field in list_fields):
        raise ValueError("Estado de feature pipeline inconsistente")
    if (
        len(state["asset_classes"]) != len(set(state["asset_classes"]))
        or not set(state["asset_classes"]).issubset({"BR_STOCK", "FII"})
        or len(state["numeric_features"]) != len(set(state["numeric_features"]))
        or len(state["rank_features"]) != len(set(state["rank_features"]))
        or len(state["feature_columns"]) != len(set(state["feature_columns"]))
    ):
        raise ValueError("Estado de feature pipeline inconsistente")
    numeric_features = _validate_raw_numeric_features(
        state["numeric_features"], context="numeric_features"
    )
    rank_features = _validate_raw_numeric_features(
        state["rank_features"], context="rank_features"
    )
    categorical_features = _validate_categorical_features(
        state["categorical_features"]
    )
    _validate_feature_names(state["feature_columns"], context="feature_columns")
    if not set(rank_features).issubset(numeric_features):
        raise ValueError("Estado de feature pipeline inconsistente")

    mapping_fields = (
        "winsor_limits",
        "numeric_medians",
        "category_vocabulary",
        "reference_numeric",
        "reference_category",
    )
    if any(not isinstance(state[field], dict) for field in mapping_fields):
        raise ValueError("Estado de feature pipeline inconsistente")
    expected_numeric_keys = set(numeric_features)
    expected_rank_keys = {f"rank__{feature}" for feature in rank_features}
    expected_sector_rank_keys = (
        {f"sector_rank__{feature}" for feature in rank_features}
        if "BR_STOCK" in state["asset_classes"]
        else set()
    )
    expected_reference_keys = (
        expected_numeric_keys | expected_rank_keys | expected_sector_rank_keys
    )
    expected_categorical_keys = set(categorical_features)
    if (
        set(state["winsor_limits"]) != expected_numeric_keys
        or set(state["numeric_medians"]) != expected_numeric_keys
        or set(state["reference_numeric"]) != expected_reference_keys
        or set(state["category_vocabulary"]) != expected_categorical_keys
        or set(state["reference_category"]) != expected_categorical_keys
    ):
        raise ValueError("Estado de feature pipeline inconsistente")

    for feature in numeric_features:
        limits = state["winsor_limits"][feature]
        if (
            not isinstance(limits, list)
            or len(limits) != 2
            or not all(_is_finite_or_none(value) for value in limits)
            or not _is_finite_or_none(state["numeric_medians"][feature])
        ):
            raise ValueError("Estado numerico de feature pipeline inconsistente")
    for feature in expected_reference_keys:
        statistics = state["reference_numeric"][feature]
        if (
            not isinstance(statistics, dict)
            or set(statistics) != _NUMERIC_DRIFT_STAT_KEYS
            or not all(_is_finite_or_none(value) for value in statistics.values())
        ):
            raise ValueError("Estado de drift numerico inconsistente")

    expected_columns: list[str] = []
    for feature in numeric_features:
        expected_columns.extend((f"missing__{feature}", feature))
    for feature in rank_features:
        expected_columns.extend((f"missing__rank__{feature}", f"rank__{feature}"))
    if "BR_STOCK" in state["asset_classes"]:
        for feature in rank_features:
            expected_columns.extend(
                (f"missing__sector_rank__{feature}", f"sector_rank__{feature}")
            )
    for feature in categorical_features:
        vocabulary = state["category_vocabulary"][feature]
        reference = state["reference_category"][feature]
        if (
            not isinstance(vocabulary, list)
            or any(not isinstance(value, str) for value in vocabulary)
            or len(vocabulary) != len(set(vocabulary))
            or UNKNOWN_CATEGORY in vocabulary
            or not isinstance(reference, dict)
            or set(reference) != _CATEGORICAL_DRIFT_STAT_KEYS
            or not all(_is_finite_or_none(value) for value in reference.values())
        ):
            raise ValueError("Estado de categorias inconsistente")
        _validate_feature_names(vocabulary, context=f"category_vocabulary[{feature}]")
        expected_columns.extend(
            _category_column(feature, category)
            for category in (*vocabulary, UNKNOWN_CATEGORY)
        )
    if state["feature_columns"] != expected_columns:
        raise ValueError("Estado de feature pipeline inconsistente")


def _finite_numeric(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame:
        return pd.Series(np.nan, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").replace([np.inf, -np.inf], np.nan)


def _asset_classes(frame: pd.DataFrame) -> tuple[str, ...]:
    if "asset_class" not in frame:
        return ()
    return tuple(sorted(frame["asset_class"].dropna().astype(str).unique()))


class FoldFeaturePipeline:
    """Serializable, train-only preprocessing for one temporal fold."""

    def __init__(
        self,
        *,
        numeric_features: Iterable[str] | None = None,
        rank_features: Iterable[str] | None = None,
        categorical_features: Iterable[str] = CATEGORICAL_FEATURES,
    ) -> None:
        self._requested_numeric_features = (
            _validate_raw_numeric_features(numeric_features, context="numeric_features")
            if numeric_features is not None
            else None
        )
        self._requested_rank_features = (
            _validate_raw_numeric_features(rank_features, context="rank_features")
            if rank_features is not None
            else None
        )
        self.categorical_features = _validate_categorical_features(categorical_features)
        self._fitted = False

    def _default_numeric_features(self, frame: pd.DataFrame) -> tuple[str, ...]:
        classes = set(_asset_classes(frame))
        groups = [
            group
            for name, group in FEATURE_GROUPS.items()
            if name not in _FII_GROUPS | _EQUITY_GROUPS
            or (name in _FII_GROUPS and "FII" in classes)
            or (name in _EQUITY_GROUPS and "BR_STOCK" in classes)
        ]
        allowed = _ordered_unique(column for group in groups for column in group)
        present_extra = [
            column
            for column in frame.columns
            if column in allowed and pd.api.types.is_numeric_dtype(frame[column])
        ]
        return _ordered_unique((*allowed, *present_extra))

    def fit(self, train: pd.DataFrame) -> "FoldFeaturePipeline":
        if train.empty:
            raise ValueError("Nao e possivel ajustar feature pipeline sem linhas")
        self.asset_classes_ = _asset_classes(train)
        self.numeric_features_ = _ordered_unique(
            self._requested_numeric_features
            if self._requested_numeric_features is not None
            else self._default_numeric_features(train)
        )
        requested_ranks = (
            self._requested_rank_features
            if self._requested_rank_features is not None
            else DEFAULT_RANK_FEATURES
        )
        self.rank_features_ = tuple(
            feature for feature in _ordered_unique(requested_ranks) if feature in self.numeric_features_
        )

        self.winsor_limits_: dict[str, tuple[float | None, float | None]] = {}
        self.numeric_medians_: dict[str, float | None] = {}
        self.reference_numeric_: dict[str, dict[str, float]] = {}
        numeric_inputs = self._numeric_inputs(train)
        for column in self.numeric_features_:
            values = numeric_inputs[column]
            finite = values.dropna()
            if finite.empty:
                lower = upper = median = None
            else:
                lower, upper = np.quantile(finite.to_numpy(dtype=float), [0.01, 0.99])
                lower, upper = float(lower), float(upper)
                median = float(finite.clip(lower, upper).median())
            self.winsor_limits_[column] = (lower, upper)
            self.numeric_medians_[column] = median
            clipped = self._clip(values, lower, upper)
            self.reference_numeric_[column] = self._summary_values(clipped)

        ranks = self._rank_inputs(train)
        for column in ranks:
            self.reference_numeric_[column] = self._summary_values(ranks[column])

        sector_ranks = self._sector_rank_inputs(train)
        for column in sector_ranks:
            self.reference_numeric_[column] = self._summary_values(sector_ranks[column])

        self.category_vocabulary_: dict[str, tuple[str, ...]] = {}
        self.reference_category_: dict[str, dict[str, float]] = {}
        for column in self.categorical_features:
            if column in train:
                normalized = train[column].dropna().astype(str)
                vocabulary = tuple(
                    sorted(
                        value
                        for value in normalized.unique()
                        if value and value != UNKNOWN_CATEGORY
                    )
                )
                _validate_feature_names(
                    vocabulary, context=f"category_vocabulary[{column}]"
                )
                missing_rate = float(train[column].isna().mean())
            else:
                vocabulary = ()
                missing_rate = 1.0
            self.category_vocabulary_[column] = vocabulary
            self.reference_category_[column] = {"missing_rate": missing_rate}

        self._fitted = True
        self.feature_columns_ = tuple(self._transform(train).columns)
        return self

    @staticmethod
    def _clip(
        values: pd.Series, lower: float | None, upper: float | None
    ) -> pd.Series:
        if lower is None or upper is None:
            return values
        return values.clip(lower, upper)

    @staticmethod
    def _summary_values(values: pd.Series) -> dict[str, float]:
        finite = values.dropna()
        return {
            "mean": float(finite.mean()) if not finite.empty else 0.0,
            "std": float(finite.std(ddof=0)) if not finite.empty else 0.0,
            "missing_rate": float(values.isna().mean()),
        }

    def _numeric_inputs(self, frame: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(
            {column: _finite_numeric(frame, column) for column in self.numeric_features_},
            index=frame.index,
        )

    def _rank_inputs(self, frame: pd.DataFrame) -> pd.DataFrame:
        ranks = pd.DataFrame(index=frame.index)
        dates = (
            pd.to_datetime(frame["date"], errors="coerce")
            if "date" in frame
            else pd.Series(pd.NaT, index=frame.index)
        )
        eligible = (
            frame["research_eligible"].fillna(False).astype(bool)
            if "research_eligible" in frame
            else pd.Series(True, index=frame.index)
        )
        for feature in self.rank_features_:
            values = _finite_numeric(frame, feature)
            output = pd.Series(np.nan, index=frame.index, dtype=float)
            eligible_values = pd.DataFrame({"date": dates, "value": values}).loc[eligible]
            for _, group in eligible_values.groupby("date", sort=False, dropna=False):
                valid = group["value"].dropna()
                if valid.empty:
                    continue
                if len(valid) == 1:
                    output.loc[valid.index] = 0.0
                    continue
                ranked = valid.rank(method="average")
                output.loc[valid.index] = 2.0 * (ranked - 1.0) / (len(valid) - 1.0) - 1.0
            ranks[f"rank__{feature}"] = output
        return ranks

    def _sector_rank_inputs(self, frame: pd.DataFrame) -> pd.DataFrame:
        ranks = pd.DataFrame(index=frame.index)
        if "BR_STOCK" not in self.asset_classes_:
            return ranks
        dates = (
            pd.to_datetime(frame["date"], errors="coerce")
            if "date" in frame
            else pd.Series(pd.NaT, index=frame.index)
        )
        eligible = (
            frame["research_eligible"].fillna(False).astype(bool)
            if "research_eligible" in frame
            else pd.Series(True, index=frame.index)
        )
        equity = (
            frame["asset_class"].eq("BR_STOCK")
            if "asset_class" in frame
            else pd.Series(False, index=frame.index)
        )
        sector = (
            frame["sector"].where(frame["sector"].notna(), UNKNOWN_CATEGORY).astype(str)
            if "sector" in frame
            else pd.Series(UNKNOWN_CATEGORY, index=frame.index)
        )
        for feature in self.rank_features_:
            values = _finite_numeric(frame, feature)
            output = pd.Series(np.nan, index=frame.index, dtype=float)
            eligible_values = pd.DataFrame(
                {"date": dates, "sector": sector, "value": values}
            ).loc[eligible & equity]
            for _, group in eligible_values.groupby(
                ["date", "sector"], sort=False, dropna=False
            ):
                valid = group["value"].dropna()
                if valid.empty:
                    continue
                if len(valid) == 1:
                    output.loc[valid.index] = 0.0
                    continue
                ranked = valid.rank(method="average")
                output.loc[valid.index] = 2.0 * (ranked - 1.0) / (len(valid) - 1.0) - 1.0
            ranks[f"sector_rank__{feature}"] = output
        return ranks

    def _transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        columns: dict[str, pd.Series] = {}
        numeric_inputs = self._numeric_inputs(frame)
        for column in self.numeric_features_:
            values = numeric_inputs[column]
            columns[f"missing__{column}"] = values.isna().astype(float)
            lower, upper = self.winsor_limits_[column]
            median = self.numeric_medians_[column]
            columns[column] = self._clip(values, lower, upper).fillna(
                0.0 if median is None else median
            )

        ranks = self._rank_inputs(frame)
        sector_ranks = self._sector_rank_inputs(frame)
        for ranked in (ranks, sector_ranks):
            for column in ranked:
                values = ranked[column]
                columns[f"missing__{column}"] = values.isna().astype(float)
                columns[column] = values.fillna(0.0)

        for feature in self.categorical_features:
            values = (
                frame[feature].where(frame[feature].notna(), UNKNOWN_CATEGORY).astype(str)
                if feature in frame
                else pd.Series(UNKNOWN_CATEGORY, index=frame.index)
            )
            vocabulary = self.category_vocabulary_[feature]
            known = values.where(values.isin(vocabulary), UNKNOWN_CATEGORY)
            for category in (*vocabulary, UNKNOWN_CATEGORY):
                columns[_category_column(feature, category)] = known.eq(category).astype(float)
        return pd.DataFrame(columns, index=frame.index)

    def transform(self, frame: pd.DataFrame) -> pd.DataFrame:
        if not self._fitted:
            raise RuntimeError("Feature pipeline precisa ser ajustado antes do transform")
        transformed = self._transform(frame)
        return transformed.loc[:, list(self.feature_columns_)]

    def fit_transform(self, train: pd.DataFrame) -> pd.DataFrame:
        return self.fit(train).transform(train)

    def to_state(self) -> dict:
        if not self._fitted:
            raise RuntimeError("Feature pipeline precisa ser ajustado antes da serializacao")
        return {
            "schema_version": PIPELINE_SCHEMA_VERSION,
            "numeric_feature_schema_version": NUMERIC_FEATURE_SCHEMA_VERSION,
            "asset_classes": list(self.asset_classes_),
            "numeric_features": list(self.numeric_features_),
            "rank_features": list(self.rank_features_),
            "categorical_features": list(self.categorical_features),
            "winsor_limits": {
                column: list(limits) for column, limits in self.winsor_limits_.items()
            },
            "numeric_medians": deepcopy(self.numeric_medians_),
            "category_vocabulary": {
                column: list(values) for column, values in self.category_vocabulary_.items()
            },
            "reference_numeric": deepcopy(self.reference_numeric_),
            "reference_category": deepcopy(self.reference_category_),
            "feature_columns": list(self.feature_columns_),
        }

    @classmethod
    def from_state(cls, state: dict) -> "FoldFeaturePipeline":
        _validate_serialized_state(state)
        pipeline = cls(
            numeric_features=state["numeric_features"],
            rank_features=state["rank_features"],
            categorical_features=state["categorical_features"],
        )
        pipeline.asset_classes_ = tuple(state["asset_classes"])
        pipeline.numeric_features_ = tuple(state["numeric_features"])
        pipeline.rank_features_ = tuple(state["rank_features"])
        pipeline.winsor_limits_ = {
            column: tuple(values) for column, values in state["winsor_limits"].items()
        }
        pipeline.numeric_medians_ = dict(state["numeric_medians"])
        pipeline.category_vocabulary_ = {
            column: tuple(values) for column, values in state["category_vocabulary"].items()
        }
        pipeline.reference_numeric_ = deepcopy(state["reference_numeric"])
        pipeline.reference_category_ = deepcopy(state["reference_category"])
        pipeline.feature_columns_ = tuple(state["feature_columns"])
        pipeline._fitted = True
        return pipeline

    def _group_for_numeric(self, feature: str) -> str:
        for group, configured in FEATURE_GROUPS.items():
            if feature in configured:
                return group
        return "unclassified"

    def feature_group_metadata(self) -> dict:
        if not self._fitted:
            raise RuntimeError("Feature pipeline precisa ser ajustado antes dos metadados")
        groups: dict[str, list[str]] = {
            "price_momentum": [],
            "volatility_risk": [],
            "liquidity": [],
            "market_relative": [],
            "macro_context": [],
            "cross_sectional_ranks": [],
        }
        for feature in self.numeric_features_:
            groups.setdefault(self._group_for_numeric(feature), []).append(feature)
        groups["cross_sectional_ranks"] = [f"rank__{item}" for item in self.rank_features_]
        if "FII" in self.asset_classes_:
            groups["fii_subtype"] = [
                column
                for column in self.feature_columns_
                if column.startswith("category__asset_subtype__")
            ]
        if "BR_STOCK" in self.asset_classes_:
            groups["equity_sector_relative"] = [
                column
                for column in self.feature_columns_
                if column.startswith("category__sector__")
                or column.startswith("category__subsector__")
                or column.startswith("sector_rank__")
            ]

        output_groups: dict[str, list[str]] = {}
        for name, raw_features in groups.items():
            columns = []
            for feature in raw_features:
                if feature in self.feature_columns_:
                    columns.append(feature)
                missing = f"missing__{feature}"
                if missing in self.feature_columns_:
                    columns.append(missing)
            output_groups[name] = list(dict.fromkeys(columns))
        ablations = {
            f"without_{name}": {
                "excluded_groups": [name],
                "excluded_features": columns,
            }
            for name, columns in output_groups.items()
            if columns
        }
        return {
            "schema_version": FEATURE_GROUP_SCHEMA_VERSION,
            "pipeline_schema_version": PIPELINE_SCHEMA_VERSION,
            "numeric_feature_schema_version": NUMERIC_FEATURE_SCHEMA_VERSION,
            "groups": output_groups,
            "ablations": ablations,
        }

    def drift_summary(self, frame: pd.DataFrame) -> dict:
        if not self._fitted:
            raise RuntimeError("Feature pipeline precisa ser ajustado antes do drift")
        numeric_inputs = self._numeric_inputs(frame)
        ranks = self._rank_inputs(frame)
        sector_ranks = self._sector_rank_inputs(frame)
        numeric: dict[str, dict[str, float | None]] = {}
        rank_inputs = pd.concat([ranks, sector_ranks], axis=1)
        for column in (*self.numeric_features_, *tuple(rank_inputs.columns)):
            if column in numeric_inputs:
                values = numeric_inputs[column]
                lower, upper = self.winsor_limits_[column]
                current = self._summary_values(self._clip(values, lower, upper))
                out_of_bounds = (
                    float(((values < lower) | (values > upper)).mean())
                    if lower is not None and upper is not None
                    else 0.0
                )
            else:
                current = self._summary_values(rank_inputs[column])
                out_of_bounds = 0.0
            reference = self.reference_numeric_[column]
            reference_mean = reference["mean"]
            scale = reference["std"]
            if reference_mean is None or scale is None:
                standardized_shift = None
            elif scale > 0:
                standardized_shift = (current["mean"] - reference_mean) / scale
            else:
                standardized_shift = 0.0
            numeric[column] = {
                "reference_mean": reference_mean,
                "current_mean": current["mean"],
                "standardized_mean_shift": standardized_shift,
                "reference_missing_rate": reference["missing_rate"],
                "current_missing_rate": current["missing_rate"],
                "out_of_bounds_rate": out_of_bounds,
            }

        categorical = {}
        for column, vocabulary in self.category_vocabulary_.items():
            values = (
                frame[column].dropna().astype(str)
                if column in frame
                else pd.Series(dtype=str)
            )
            categorical[column] = {
                "reference_missing_rate": self.reference_category_[column]["missing_rate"],
                "current_missing_rate": (
                    float(frame[column].isna().mean()) if column in frame else 1.0
                ),
                "unknown_rate": (
                    float((~values.isin(vocabulary)).sum() / len(frame)) if len(frame) else 0.0
                ),
            }
        return {
            "schema_version": DRIFT_SCHEMA_VERSION,
            "pipeline_schema_version": PIPELINE_SCHEMA_VERSION,
            "row_count": int(len(frame)),
            "numeric": numeric,
            "categorical": categorical,
        }
