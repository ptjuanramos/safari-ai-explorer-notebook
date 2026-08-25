import numpy as np
import pandas as pd
import geopandas as gpd
import ee

from ee import ImageCollection
from dataclasses import dataclass
from shapely.geometry import box
from antecedent_precipitation_index import AntecedentPrecipitationIndex, DailyObservation


@dataclass
class IMERGProvider:
    """
    Provider for retrieving accumulated GPM IMERG daily precipitation data.

    Same grid/pixel_id contract as CHIRPSProvider. IMERG is natively half-hourly
    in mm/hr, so daily images are built by summing each day's half-hourly
    granules * 0.5 before reducing to grid cells.
    """

    resolution_deg: float = 0.1  # IMERG native ~0.1°, vs CHIRPS 0.05°

    COLLECTION_ID = "NASA/GPM_L3/IMERG_V07"
    COORDINATES_MODE = "EPSG:4326"
    SCALE_M = 11132  # ~0.1° at equator, vs CHIRPS 5566

    def frame_grid(self, bounds: tuple[float, float, float, float]) -> gpd.GeoDataFrame:
        minx, miny, maxx, maxy = bounds
        r = self.resolution_deg

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

        return gpd.GeoDataFrame(rows, crs=IMERGProvider.COORDINATES_MODE)

    def _daily_image(self, day: pd.Timestamp) -> ee.Image:
        day_start = day.strftime("%Y-%m-%d")
        day_end = (day + pd.Timedelta(days=1)).strftime("%Y-%m-%d")

        half_hourly = (
            ee.ImageCollection(self.COLLECTION_ID)
            .filterDate(day_start, day_end)
            .select("precipitation")
        )

        granule_count = half_hourly.size().getInfo()
        if granule_count == 0:
            raise ValueError(f"no IMERG granules available for {day_start}")

        return (
            half_hourly.map(lambda img: img.multiply(0.5))
            .sum()
            .rename("precipitation")
            .set("system:time_start", ee.Date(day_start).millis())
            .set("date_str", day_start)
        )

    def get_accumulated_precipitation(
            self,
            grid: gpd.GeoDataFrame,
            start_date: str,
            end_date: str
    ) -> tuple[gpd.GeoDataFrame, ImageCollection]:

        start = pd.to_datetime(start_date)
        end = pd.Timestamp(end_date) + pd.Timedelta(days=1)  # exclusive, matches CHIRPS convention

        days = pd.date_range(start, end - pd.Timedelta(days=1), freq="D")
        daily_images = [self._daily_image(d) for d in days]
        image_collection = ee.ImageCollection(daily_images)

        accumulated_image = image_collection.sum().rename("rain_mm")

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
            scale=self.SCALE_M,
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

        api = AntecedentPrecipitationIndex()
        end = pd.Timestamp(date)
        start = end - pd.Timedelta(days=lookback_days - 1)
        days = pd.date_range(start, end, freq="D")

        daily_images = [self._daily_image(d) for d in days]
        image_collection = ee.ImageCollection(daily_images).sort("system:time_start")

        n_days = image_collection.size().getInfo()
        if n_days != lookback_days:
            raise ValueError(
                f"expected {lookback_days} daily images, got {n_days} "
                "- check IMERG coverage/latency for this window"
            )

        stacked = image_collection.toBands()
        band_names = stacked.bandNames().getInfo()  # same toBands() naming fix as CHIRPS

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
            scale=self.SCALE_M,
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
                    t_avg=20.0,  # TODO: same placeholder as CHIRPS, unvalidated
                )
                for i in range(n_days)
            ]
            decayed_by_pixel[pixel_id] = api.compute(observations)

        result = grid.copy()
        result["rain_mm"] = result["pixel_id"].map(decayed_by_pixel)
        return result, image_collection