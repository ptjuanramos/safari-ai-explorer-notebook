import numpy as np
import pandas as pd
import geopandas as gpd
import ee

from ee import ImageCollection
from dataclasses import dataclass
from shapely.geometry import box
from antecedent_precipitation_index import AntecedentPrecipitationIndex, DailyObservation

@dataclass
class CHIRPSProvider:
    """
        Provider for retrieving accumulated CHIRPS daily precipitation data.

        The provider creates a regular spatial grid aligned to the configured
            CHIRPS resolution and retrieves accumulated rainfall for each grid cell
            from Google Earth Engine.
    """

    resolution_deg: float = 0.05

    COLLECTION_ID = "UCSB-CHG/CHIRPS/DAILY"
    COORDINATES_MODE = "EPSG:4326"

    def frame_grid(self, bounds: tuple[float, float, float, float]) -> gpd.GeoDataFrame:
        minx, miny, maxx, maxy = bounds
        r = self.resolution_deg

        #Frame coordinates in the ranges of each degree -> [floor(resolution_deg), ceil(resolution_deg + x_coordinate))
        # For example: [35.12, 12.23) -> [35.10, 12.20)

        minx = np.floor(minx / r) * r
        miny = np.floor(miny / r) * r
        maxx = np.ceil(maxx / r) * r
        maxy = np.ceil(maxy / r) * r

        xs = np.arange(minx, maxx, r)
        ys = np.arange(miny, maxy, r)

        rows = [
            {"pixel_id": i, "geometry": box(x, y, x + r, y + r)}
            for i, (x, y) in enumerate((x, y) for x in xs for y in ys)
        ]

        return gpd.GeoDataFrame(rows, crs=CHIRPSProvider.COORDINATES_MODE)

    def get_accumulated_precipitation(
            self,
            grid: gpd.GeoDataFrame,
            start_date: str,
            end_date: str
    ) -> tuple[gpd.GeoDataFrame, ImageCollection]:

        """
        Each row contains:
            - `pixel_id`: Unique identifier for the grid cell.
            - `geometry`: Polygon representing the grid cell.

            The returned GeoDataFrame uses EPSG:4326 (Equals from OSMx).

        :return: GeoDataFrame: Grid cells covering the requested bounds.
        """

        start = pd.to_datetime(start_date)
        end = (pd.Timestamp(end_date) + pd.Timedelta(days=1)) #end date is exclusive, adding 1 day

        image_collection = (
            ee.ImageCollection(CHIRPSProvider.COLLECTION_ID)
            .filterDate(start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"))
        )

        accumulated_image = (
            image_collection
            .sum()
            .rename("rain_mm")
        )

        features = [
            ee.Feature(
                ee.Geometry.Rectangle(list(row.geometry.bounds)),
                {"pixel_id": int(row.pixel_id)},
            )
            for row in grid.itertuples()
        ]

        fc = ee.FeatureCollection(features)

        reduced = accumulated_image.reduceRegions(
            collection=fc,
            reducer=ee.Reducer.mean(),
            scale=5566,
        ).getInfo()

        rain_by_pixel = {
            f["properties"]["pixel_id"]: f["properties"].get("mean")
            for f in reduced["features"]
        }

        result = grid.copy()
        result["rain_mm"] = result["pixel_id"].map(rain_by_pixel)
        return result, image_collection

    def get_decayed_precipitation(
            self,
            grid: gpd.GeoDataFrame,
            date: str,
            lookback_days: int
    ) -> tuple[gpd.GeoDataFrame, ImageCollection]:

        """
        Same grid/pixel_id contract as get_accumulated_precipitation, but rain_mm
        is now a decay-weighted API value instead of a flat window sum.
        """

        api = AntecedentPrecipitationIndex()
        end = pd.Timestamp(date)
        start = end - pd.Timedelta(days=lookback_days - 1)
        query_end = end + pd.Timedelta(days=1)  # exclusive, matches existing convention

        image_collection = (
            ee.ImageCollection(self.COLLECTION_ID)
            .filterDate(start.strftime("%Y-%m-%d"), query_end.strftime("%Y-%m-%d"))
            .sort("system:time_start")  # oldest -> newest, so band order is predictable
            .select("precipitation")
        )

        n_days = image_collection.size().getInfo()
        if n_days != lookback_days:
            raise ValueError(
                f"expected {lookback_days} daily images, got {n_days} "
                "- check CHIRPS coverage for this window"
            )

        stacked = image_collection.toBands()
        band_names = stacked.bandNames().getInfo()

        features = [
            ee.Feature(
                ee.Geometry.Rectangle(list(row.geometry.bounds)),
                {"pixel_id": int(row.pixel_id)},
            )
            for row in grid.itertuples()
        ]
        fc = ee.FeatureCollection(features)

        reduced = stacked.reduceRegions(
            collection=fc,
            reducer=ee.Reducer.mean(),
            scale=5566,
        ).getInfo()

        decayed_by_pixel = {}
        for f in reduced["features"]:
            props = f["properties"]
            pixel_id = props["pixel_id"]

            observations = [
                DailyObservation(
                    days_ago=(n_days - 1) - i,
                    rain_mm=props.get(band_names[i]) or 0.0,
                    t_clt=20.0,
                    t_avg=20.0,  # TODO: fixed for now — no temperature term until this is validated
                )
                for i in range(n_days)
            ]
            decayed_by_pixel[pixel_id] = api.compute(observations)

        result = grid.copy()
        result["rain_mm"] = result["pixel_id"].map(decayed_by_pixel)
        return result, image_collection