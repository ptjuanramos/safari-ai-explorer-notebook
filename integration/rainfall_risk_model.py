from dataclasses import dataclass
import pandas as pd

@dataclass
class RainfallRiskModel:

    """
    Model for converting accumulated rainfall into a normalized rainfall risk.
    The model uses configurable rainfall thresholds to map accumulated, to a risk score between 0 and 1.

    Default thresholds:
        - >= 30 mm -> 1.0
        - >= 15 mm -> 0.6
        - >= 5 mm  -> 0.3
        - >= 0 mm  -> 0.0


    TODO:
        - Improve the rainfall-risk model to account for additional factors such
        as soil type, drainage capacity, terrain, rainfall duration, and
        antecedent moisture conditions.
        - Thresholds should also account for the rainfall accumulation period.
        The same accumulated rainfall can represent significantly different
        risk levels depending on whether it occurred over one day or several
        days.
    """
    thresholds: tuple[tuple[float, float], ...] = (
        (30.0, 1.0),
        (15.0, 0.6),
        (5.0, 0.3),
        (0.0, 0.0),
    )

    def risk_for(self, accumulated_mm: float) -> float:
        """
        :param accumulated_mm:
        :return:  Risk score between 0.0 and 1.0 corresponding to the highest rainfall threshold.
        """
        if pd.isna(accumulated_mm):
            return 0.0
        for min_mm, risk in self.thresholds:
            if accumulated_mm >= min_mm:
                return risk
        return 0.0