import geopandas as gpd
import numpy as np

from dataclasses import dataclass, field
from rainfall_risk_model import RainfallRiskModel
from road_rain_vulnerability import RoadRainVulnerability

@dataclass
class EdgeRiskEnricher:

    """
    Spatially joins edges to rainfall pixels, then combines
        the existing road-type base risk with the rainfall risk, weighted by how
        rain-vulnerable that road type is.
    """

    base_road_risk: dict
    default_base_risk: float = 0.5
    rain_risk_model: RainfallRiskModel = field(default_factory=RainfallRiskModel)
    vulnerability: RoadRainVulnerability = field(default_factory=RoadRainVulnerability)
    risk_weight_minutes: float = 60.0  # minutes penalty for surface_risk = 1.0

    def _base_risk_for(self, road_type) -> float:
        if isinstance(road_type, list):
            road_type = road_type[0]
        return self.base_road_risk.get(str(road_type), self.default_base_risk)

    def enrich(self, edges: gpd.GeoDataFrame, rain_pixels: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
            Calculate rainfall-related surface risk for road edges with extra attributes:

            - `rain_risk`
            - `base_road_risk`
            - `road_vulnerability`
            - `surface_risk`: `min(1, base_road_risk + road_vulnerability * rain_risk)`

            :param edges: OSMnx road edges.
            :type edges: GeoDataFrame
            :param rain_pixels: Extracted rainfall pixels containing rainfall data.
            :type rain_pixels: GeoDataFrame

            :return: Complementary edges dataframe with extra attributes
            :rtype: GeoDataFrame
        """
        joined = gpd.sjoin(
            edges.reset_index(),
            rain_pixels[["pixel_id", "rain_mm", "geometry"]],
            how="left",
            predicate="intersects",
        )

        # TODO: need review - an edge can straddle more than one pixel; take the worst (highest) rainfall it touches
        worst_rain = joined.groupby(["u", "v", "key"])["rain_mm"].max()

        edges = edges.copy()
        edges["rain_mm"] = edges.apply(
            lambda row: worst_rain.get((row.name[0], row.name[1], row.name[2]), np.nan),
            axis=1,
        )
        edges["rain_risk"] = edges["rain_mm"].apply(self.rain_risk_model.risk_for)
        edges["base_road_risk"] = edges["road_type"].apply(self._base_risk_for)
        edges["road_vulnerability"] = edges["road_type"].apply(self.vulnerability.factor_for)

        edges["surface_risk"] = np.minimum(
            1.0,
            edges["base_road_risk"] + edges["road_vulnerability"] * edges["rain_risk"],
        )
        edges["cost"] = edges["travel_time_m"] + self.risk_weight_minutes * edges["surface_risk"]
        return edges