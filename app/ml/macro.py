from __future__ import annotations

import pandas as pd


def merge_released_macro(features: pd.DataFrame, releases: pd.DataFrame) -> pd.DataFrame:
    """Adds macro observations according to their real publication timestamp."""
    if "date" not in features:
        raise ValueError("Features sem coluna date")
    required = {"reference_date", "available_at"}
    missing = required.difference(releases.columns)
    if missing:
        raise ValueError(f"Macro point-in-time exige {sorted(missing)}")
    value_columns = [column for column in releases.columns if column not in required]
    if not value_columns:
        raise ValueError("Macro sem valores")

    left = features.copy()
    left["date"] = pd.to_datetime(left["date"], utc=False).dt.tz_localize(None)
    left["_feature_cutoff"] = left["date"].dt.normalize() + pd.Timedelta(days=1) - pd.Timedelta(nanoseconds=1)
    right = releases.copy()
    right["reference_date"] = pd.to_datetime(
        right["reference_date"], utc=False
    ).dt.tz_localize(None)
    right["available_at"] = pd.to_datetime(right["available_at"], utc=False).dt.tz_localize(None)
    if right[["reference_date", "available_at"]].isna().any().any():
        raise ValueError("Macro point-in-time contem datas invalidas")
    if (right["reference_date"] > right["available_at"]).any():
        raise ValueError("Macro point-in-time tem reference_date posterior a available_at")
    right = right.sort_values("available_at", kind="stable")
    snapshots: list[dict] = []
    state: dict = {}
    reference_state: dict[str, pd.Timestamp] = {}
    for available_at, released_group in right.groupby("available_at", sort=True):
        updated = False
        for _, release in released_group.iterrows():
            for column in value_columns:
                if pd.notna(release[column]):
                    state[column] = release[column]
                    reference_state[column] = release["reference_date"]
                    updated = True
        if not updated:
            raise ValueError("Macro point-in-time contem release sem valores")
        snapshot = {
            "available_at": available_at,
            "reference_date": max(reference_state.values()),
            **state,
        }
        snapshot.update(
            {
                f"{column}_reference_date": reference_state.get(column, pd.NaT)
                for column in value_columns
            }
        )
        snapshots.append(snapshot)
    right = pd.DataFrame(snapshots).sort_values("available_at")
    merged = pd.merge_asof(
        left.sort_values("_feature_cutoff"),
        right,
        left_on="_feature_cutoff",
        right_on="available_at",
        direction="backward",
        allow_exact_matches=True,
    )
    return merged.drop(columns=["_feature_cutoff", "available_at"]).sort_values(
        [column for column in ("ticker", "date") if column in merged]
    ).reset_index(drop=True)
