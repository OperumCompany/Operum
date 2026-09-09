from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ConformalInterval:
    coverage: float
    radius: float

    @classmethod
    def fit(cls, absolute_residuals, *, coverage: float = 0.80) -> "ConformalInterval":
        if not 0 < coverage < 1:
            raise ValueError("coverage deve estar entre 0 e 1")
        residuals = np.asarray(absolute_residuals, dtype=float)
        residuals = np.sort(residuals[np.isfinite(residuals)])
        if residuals.size == 0:
            raise ValueError("residuos validos sao obrigatorios")
        rank = min(residuals.size, int(np.ceil((residuals.size + 1) * coverage)))
        return cls(coverage=coverage, radius=round(float(residuals[rank - 1]), 12))

    def bounds(self, predictions) -> tuple[np.ndarray, np.ndarray]:
        center = np.asarray(predictions, dtype=float)
        return center - self.radius, center + self.radius

