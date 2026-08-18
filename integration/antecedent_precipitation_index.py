import math
from dataclasses import dataclass

@dataclass
class DailyObservation:
    days_ago: int
    rain_mm: float
    t_clt: float
    t_avg: float


class AntecedentPrecipitationIndex:
    """
    Computes a decay-weighted Antecedent Precipitation Index (API) from daily
    rainfall, using a temperature-adaptive recession coefficient (Crozier & Eyles
    1980, extended by De Moraes et al. 2024).
    """

    def __init__(self, grid=None, k_opt: float = 0.84, delta: float = 0.012):
        self.k_opt = k_opt
        self.delta = delta
        self.grid = grid

    def _recession_coefficient(self, t_clt: float, t_avg: float) -> float:
        return self.k_opt + self.delta * (t_clt - t_avg)

    def _compute_single(self, d: int, current_rain_mm: float, t_clt: float, t_avg: float) -> float:
        return current_rain_mm * math.pow(self._recession_coefficient(t_clt, t_avg), d)

    def compute(self, daily_observations: list[DailyObservation]) -> float:
        return sum(
            self._compute_single(obs.days_ago, obs.rain_mm, obs.t_clt, obs.t_avg)
            for obs in daily_observations
        )