from __future__ import annotations

import numpy as np
import pandas as pd

from app.ml.probabilistic import (
    CENTER_OBJECTIVES,
    QUANTILE_ALPHAS,
    make_xgboost_center,
    make_xgboost_classifier,
    make_xgboost_quantile,
    ordered_quantiles,
)


def test_real_xgboost_213_fits_locked_classifier_centers_and_separate_quantiles():
    values = np.linspace(-1.0, 1.0, 64)
    matrix = pd.DataFrame({"signal": values, "signal_squared": values**2})
    truth = values * 0.05 + np.sin(values * 4.0) * 0.01
    labels = (truth > 0.0).astype(int)

    classifier = make_xgboost_classifier(seed=17, n_estimators=4, max_depth=2)
    classifier.fit(matrix, labels)
    probabilities = classifier.predict_proba(matrix)[:, 1]
    assert np.all(np.isfinite(probabilities))
    assert np.all((probabilities >= 0.0) & (probabilities <= 1.0))

    for objective in CENTER_OBJECTIVES:
        center = make_xgboost_center(
            objective=objective,
            seed=17,
            n_estimators=4,
            max_depth=2,
        )
        center.fit(matrix, truth)
        assert np.all(np.isfinite(center.predict(matrix)))

    quantile_models = {
        name: make_xgboost_quantile(
            alpha=alpha,
            seed=17,
            n_estimators=4,
            max_depth=2,
        )
        for name, alpha in zip(("q10", "q50", "q90"), QUANTILE_ALPHAS)
    }
    raw = {}
    for name, model in quantile_models.items():
        model.fit(matrix, truth)
        raw[name] = model.predict(matrix)
    quantiles = ordered_quantiles(raw)
    assert np.all(quantiles["q10"] <= quantiles["q50"])
    assert np.all(quantiles["q50"] <= quantiles["q90"])
