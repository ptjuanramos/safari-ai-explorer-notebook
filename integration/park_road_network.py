from dataclasses import dataclass
import geopandas as gpd
import osmnx as ox

@dataclass
class ParkRoadNetwork:
    place_name: str
    exclude_road_types: tuple[str, ...] = ("footway", "path")

    def _is_vehicle_road(self, road_type) -> bool:
        if not isinstance(road_type, list):
            road_type = [road_type]
        return not any(r in self.exclude_road_types for r in road_type)

    def load(self) -> tuple[gpd.GeoDataFrame, gpd.GeoDataFrame]:
        graph = ox.graph_from_place(self.place_name, network_type="all", retain_all=True)
        graph = ox.add_edge_speeds(graph)
        graph = ox.add_edge_travel_times(graph)

        nodes, edges = ox.graph_to_gdfs(graph)
        edges = edges.rename(columns={
            "highway": "road_type",
            "length": "length_m",
            "travel_time": "travel_time_s",
        })
        edges["travel_time_m"] = edges["travel_time_s"] / 60

        edges = edges[edges["road_type"].apply(self._is_vehicle_road)].copy()
        return nodes, edges