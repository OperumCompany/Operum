from __future__ import annotations

from datetime import datetime, timezone

import numpy as np
import pandas as pd

from app.ml.features import build_point_in_time_features
from app.ml.forecasting import BaselineForecaster, PUBLIC_HORIZONS, build_horizon_output
from app.ml.macro import merge_released_macro
from app.ml.training import load_model_package


class VersionedForecaster:
    def __init__(self, repository, *, stage: str = "active"):
        self.repository = repository
        if stage not in {"active", "shadow"}:
            raise ValueError("Stage de inferencia invalido")
        self.stage = stage
        self.baseline = BaselineForecaster()

    def _model_record(self, asset_class: str, horizon_days: int) -> dict | None:
        if self.stage == "active":
            if hasattr(self.repository, "get_serving_model"):
                return self.repository.get_serving_model(asset_class, horizon_days)
            return self.repository.get_active_model(asset_class, horizon_days)
        return next(
            (
                item
                for item in self.repository.list_model_versions(status="shadow")
                if item["asset_class"] == asset_class
                and int(item["horizon_days"]) == int(horizon_days)
            ),
            None,
        )

    @staticmethod
    def _confidence(metadata: dict) -> float:
        candidate_mae = float(metadata.get("metrics", {}).get("candidate", {}).get("mae", 1.0))
        baseline_mae = float(metadata.get("metrics", {}).get("baseline", {}).get("mae", 1.0))
        improvement = max(-0.25, min(0.35, (baseline_mae - candidate_mae) / max(baseline_mae, 1e-9)))
        radius = float(metadata.get("interval", {}).get("radius", 0.25))
        width_penalty = min(0.25, radius * 0.5)
        return float(np.clip(0.50 + improvement - width_penalty, 0.15, 0.85))

    def forecast(
        self,
        ticker: str,
        asset_class: str,
        market: pd.DataFrame,
        context: pd.DataFrame | None = None,
        macro_releases: pd.DataFrame | None = None,
    ) -> dict:
        if market.empty:
            raise ValueError("Historico de mercado vazio")
        normalized = market.copy()
        normalized["ticker"] = ticker.upper()
        normalized["asset_class"] = asset_class
        normalized["date"] = pd.to_datetime(normalized["date"])
        baseline = self.baseline.forecast(ticker, normalized["close"])
        featured = build_point_in_time_features(normalized, context=context)
        if macro_releases is not None:
            featured = merge_released_macro(featured, macro_releases)
        latest = featured.sort_values("date").iloc[-1]
        last_price = float(latest["close"])
        model_versions: dict[str, str] = {}
        used_model = False

        for label, horizon_days in PUBLIC_HORIZONS.items():
            record = self._model_record(asset_class, horizon_days)
            if not record:
                continue
            package = load_model_package(record["metadata_path"])
            metadata = package["metadata"]
            columns = metadata["feature_columns"]
            medians = metadata.get("feature_medians", {})
            values = {
                column: float(latest[column]) if column in latest and pd.notna(latest[column]) else float(medians.get(column, 0.0))
                for column in columns
            }
            matrix = pd.DataFrame([values], columns=columns).replace([np.inf, -np.inf], np.nan).fillna(medians)
            expected_return = float(package["model"].predict(matrix)[0])
            radius = float(metadata.get("interval", {}).get("radius", 0.20))
            baseline["horizons"][label] = build_horizon_output(
                last_price=last_price,
                expected_return=expected_return,
                interval_radius=radius,
                confidence_score=self._confidence(metadata),
                horizon_days=horizon_days,
                source="xgboost",
            )
            model_versions[label] = str(record["id"])
            used_model = True

        cutoff = pd.Timestamp(normalized["date"].max())
        if cutoff.tzinfo is None:
            cutoff = cutoff.tz_localize("UTC")
        age_hours = (datetime.now(timezone.utc) - cutoff.to_pydatetime()).total_seconds() / 3600
        baseline.update(
            {
                "data_cutoff": cutoff.isoformat(),
                "generation_mode": (
                    "model"
                    if used_model and len(model_versions) == len(PUBLIC_HORIZONS)
                    else "mixed"
                    if used_model
                    else "baseline"
                ),
                "model_versions": model_versions,
                "is_stale": age_hours > 72,
            }
        )
        return baseline
