
import hashlib
import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import NamedTuple

import ee
import numpy as np
import pandas as pd
import requests
from pyproj import Transformer

GBIF_URL = "https://api.gbif.org/v1/occurrence/search"
EMBEDDING_COLLECTION = "GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL"
UTM = "EPSG:32736"
BAND_COLS = [f"A{i:02d}" for i in range(64)]
GBIF_COLUMNS = ["gbifID", "decimalLongitude", "decimalLatitude", "year"]

to_utm = Transformer.from_crs("EPSG:4326", UTM, always_xy=True)
to_lonlat = Transformer.from_crs(UTM, "EPSG:4326", always_xy=True)


@dataclass(frozen=True)
class BuffaloConfig:

    bounds: tuple = (34.0, -3.6, 36.0, -1.6)
    start_year: int = 2017
    end_year: int = 2025
    buffer_m: int = 700
    scale_m: int = 10
    cell_size_m: int = 10_000
    thin_cell_m: int = 1_000
    n_per_presence: int = 10
    seed: int = 42
    camera_year: int = 2017
    min_agreement: float = 0.5
    min_trap_days: int = 30
    camera_dir: str = "data"
    cache_dir: str | None = None

    def key(self) -> str:
        settings = {k: v for k, v in asdict(self).items() if k not in ("cache_dir", "camera_dir")}
        return hashlib.sha1(json.dumps(settings, sort_keys=True).encode()).hexdigest()[:10]


DEFAULT_CONFIG = BuffaloConfig()


class BuffaloDataset(NamedTuple):
    presences: pd.DataFrame
    mammals: pd.DataFrame
    visited_cells: set
    sdm_df: pd.DataFrame
    cameras: pd.DataFrame


def cached(config: BuffaloConfig, name: str, build) -> pd.DataFrame:
    if config.cache_dir is None:
        return build()
    path = Path(config.cache_dir) / f"buffalo_{name}_{config.key()}.parquet"
    if path.exists():
        print(f"{name}: loaded from {path}")
        return pd.read_parquet(path)
    df = build()
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)
    return df


def _in_box(df: pd.DataFrame, bounds) -> pd.Series:
    west, south, east, north = bounds
    return df["decimalLongitude"].between(west, east) & df["decimalLatitude"].between(south, north)


def get_page(params: dict, retries: int = 5) -> dict:
    for attempt in range(retries):
        try:
            r = requests.get(GBIF_URL, params=params, timeout=120)
            r.raise_for_status()
            return r.json()
        except requests.RequestException as e:
            print(f"retry {attempt + 1}/{retries} at offset {params['offset']}: {e}")
            time.sleep(5 * (attempt + 1))
    raise RuntimeError(f"GBIF failed {retries} times at offset {params['offset']}")


def fetch_all(params: dict) -> pd.DataFrame:
    rows, offset = [], 0
    while True:
        j = get_page({**params, "offset": offset, "limit": 300})
        rows.extend(j["results"])
        if j["endOfRecords"]:
            break
        offset += 300
    return pd.DataFrame(rows)


def fetch_buffalo_presences(config: BuffaloConfig = DEFAULT_CONFIG) -> pd.DataFrame:

    def build():
        df = fetch_all({"scientificName": "Syncerus caffer", "country": "TZ",
                        "hasCoordinate": "true", "hasGeospatialIssue": "false"})
        df = df[df["year"].between(config.start_year, config.end_year) & _in_box(df, config.bounds)]
        return df[GBIF_COLUMNS].astype({"gbifID": str}).reset_index(drop=True)

    presences = cached(config, "presences", build)
    print("buffalo sightings in box:", len(presences))
    return presences


def fetch_mammals(config: BuffaloConfig = DEFAULT_CONFIG) -> pd.DataFrame:
    west, south, east, north = config.bounds
    params = {
        "classKey": 359,
        "decimalLongitude": f"{west},{east}",
        "decimalLatitude": f"{south},{north}",
        "hasCoordinate": "true",
        "hasGeospatialIssue": "false",
    }

    def build():
        yearly = []
        for year in range(config.start_year, config.end_year + 1):
            year_df = fetch_all({**params, "year": year})
            print(year, len(year_df))
            yearly.append(year_df[GBIF_COLUMNS])
        return pd.concat(yearly, ignore_index=True).astype({"gbifID": str})

    mammals = cached(config, "mammals", build)
    print("mammal sightings in box:", len(mammals))
    return mammals


def fetch_mammal_records(config: BuffaloConfig = DEFAULT_CONFIG) -> pd.DataFrame:
    west, south, east, north = config.bounds
    params = {
        "classKey": 359,
        "decimalLongitude": f"{west},{east}",
        "decimalLatitude": f"{south},{north}",
        "hasCoordinate": "true",
        "hasGeospatialIssue": "false",
    }
    columns = GBIF_COLUMNS + ["speciesKey", "species"]

    def build():
        yearly = []
        for year in range(config.start_year, config.end_year + 1):
            year_df = fetch_all({**params, "year": year}).reindex(columns=columns)
            print(year, len(year_df))
            yearly.append(year_df)
        return pd.concat(yearly, ignore_index=True).astype({"gbifID": str, "species": str})

    records = cached(config, "mammal_records", build)
    print("mammal records in box:", len(records))
    return records


def thin_presences(presences: pd.DataFrame, config: BuffaloConfig = DEFAULT_CONFIG) -> pd.DataFrame:
    x, y = to_utm.transform(presences["decimalLongitude"].values, presences["decimalLatitude"].values)
    return (presences.assign(cx=x // config.thin_cell_m, cy=y // config.thin_cell_m)
            .drop_duplicates(subset=["cx", "cy", "year"])
            .drop(columns=["cx", "cy"])
            .reset_index(drop=True))


def find_visited_cells(mammals: pd.DataFrame, config: BuffaloConfig = DEFAULT_CONFIG) -> set:
    x, y = to_utm.transform(mammals["decimalLongitude"].values, mammals["decimalLatitude"].values)
    return set(zip((x // config.cell_size_m).astype(int), (y // config.cell_size_m).astype(int)))


def make_presence_background(presences: pd.DataFrame, bbox, visited_cells: set,
                             config: BuffaloConfig = DEFAULT_CONFIG) -> pd.DataFrame:
    min_lon, min_lat, max_lon, max_lat = bbox
    rng = np.random.default_rng(config.seed)

    corner_x, corner_y = to_utm.transform([min_lon, max_lon, min_lon, max_lon], [min_lat, min_lat, max_lat, max_lat])
    x_min, x_max = min(corner_x), max(corner_x)
    y_min, y_max = min(corner_y), max(corner_y)

    pres_x, pres_y = to_utm.transform(presences["decimalLongitude"].values, presences["decimalLatitude"].values)
    pres_years = presences["year"].values

    years = np.repeat(pres_years, config.n_per_presence)

    rows = []
    for i, year in enumerate(years):
        same_year = pres_years == year
        while True:
            x, y = rng.uniform(x_min, x_max), rng.uniform(y_min, y_max)
            if (int(x // config.cell_size_m), int(y // config.cell_size_m)) not in visited_cells:
                continue
            lon, lat = to_lonlat.transform(x, y)
            if not (min_lon <= lon <= max_lon and min_lat <= lat <= max_lat):
                continue
            if np.hypot(pres_x[same_year] - x, pres_y[same_year] - y).min() < config.buffer_m:
                continue
            break
        rows.append({"point_id": f"bg_{i}", "decimalLongitude": lon, "decimalLatitude": lat, "year": year})

    background = pd.DataFrame(rows).assign(presence=0)
    presence = (presences[["gbifID", "decimalLongitude", "decimalLatitude", "year"]]
                .rename(columns={"gbifID": "point_id"})
                .assign(presence=1))
    return pd.concat([presence, background], ignore_index=True)


def get_range_year_reduced_area_embeddings(points_df: pd.DataFrame, id_col: str, start_year: int, end_year: int,
                                           config: BuffaloConfig = DEFAULT_CONFIG) -> list:
    reduced_area_embeddings = []

    for year in range(start_year, end_year + 1):
        img = ee.ImageCollection(EMBEDDING_COLLECTION).filterDate(f"{year}-01-01", f"{year + 1}-01-01").mosaic()

        yearly_features = []
        for _, row in points_df[(points_df["year"] == year)].iterrows():
            geom = ee.Geometry.Point([row["decimalLongitude"], row["decimalLatitude"]]).buffer(config.buffer_m)
            yearly_features.append(ee.Feature(geom, {id_col: row[id_col]}))

        fc = ee.FeatureCollection(yearly_features)
        reduced_area = img.reduceRegions(collection=fc, reducer=ee.Reducer.mean(), scale=config.scale_m)
        reduced_area_embeddings.append(reduced_area.getInfo())
        print(f"{year}: {len(yearly_features)} points embedded")

    return reduced_area_embeddings


def embed_points(points_df: pd.DataFrame, id_col: str, config: BuffaloConfig = DEFAULT_CONFIG) -> pd.DataFrame:
    years = points_df["year"].astype(int)
    info = get_range_year_reduced_area_embeddings(points_df, id_col, years.min(), years.max(), config=config)
    emb = pd.DataFrame([f["properties"] for year_info in info for f in year_info["features"]])
    return points_df.merge(emb, on=id_col, how="left")


COVARIATE_COLS = ["dist_river_m", "ndvi_dry", "ndvi_wet", "tree_cover_pct", "elevation_m", "slope_deg"]
COVARIATE_SCALE_M = 30
RIVER_MIN_UPLAND_KM2 = 100
RIVER_SEARCH_M = 50_000


def covariate_image(year: int) -> ee.Image:
    rivers = (ee.FeatureCollection("WWF/HydroSHEDS/v1/FreeFlowingRivers")
              .filter(ee.Filter.gte("UPLAND_SKM", RIVER_MIN_UPLAND_KM2)))
    dist_river = rivers.distance(searchRadius=RIVER_SEARCH_M, maxError=100).unmask(RIVER_SEARCH_M).rename("dist_river_m")

    ndvi = ee.ImageCollection("MODIS/061/MOD13Q1").select("NDVI")
    ndvi_dry = ndvi.filterDate(f"{year}-07-01", f"{year}-11-01").mean().multiply(0.0001).rename("ndvi_dry")
    ndvi_wet = ndvi.filterDate(f"{year}-03-01", f"{year}-06-01").mean().multiply(0.0001).rename("ndvi_wet")

    tree_cover = (ee.ImageCollection("MODIS/061/MOD44B").select("Percent_Tree_Cover")
                  .filterDate("2000-01-01", f"{year + 1}-01-01")
                  .sort("system:time_start", False).first().rename("tree_cover_pct"))

    srtm = ee.Image("USGS/SRTMGL1_003")
    return ee.Image.cat([dist_river, ndvi_dry, ndvi_wet, tree_cover,
                         srtm.rename("elevation_m"), ee.Terrain.slope(srtm).rename("slope_deg")])


def _buffer_means(points_df: pd.DataFrame, id_col: str, image_for_year, columns: list, label: str,
                  config: BuffaloConfig, chunk: int) -> pd.DataFrame:
    reducer = ee.Reducer.mean().setOutputs(columns) if len(columns) == 1 else ee.Reducer.mean()
    rows = []
    for year in sorted(points_df["year"].astype(int).unique()):
        image = image_for_year(year)
        part = points_df[points_df["year"] == year]
        for start in range(0, len(part), chunk):
            fc = ee.FeatureCollection([
                ee.Feature(ee.Geometry.Point([p["decimalLongitude"], p["decimalLatitude"]]).buffer(config.buffer_m), {id_col: p[id_col]})
                for _, p in part.iloc[start:start + chunk].iterrows()
            ])
            reduced = image.reduceRegions(collection=fc, reducer=reducer, scale=COVARIATE_SCALE_M, tileScale=4)
            rows += [f["properties"] for f in reduced.getInfo()["features"]]
        print(f"{year}: {len(part)} points, {label}")
    return points_df.merge(pd.DataFrame(rows)[[id_col] + columns], on=id_col, how="left")


def add_covariates(points_df: pd.DataFrame, id_col: str, config: BuffaloConfig = DEFAULT_CONFIG,
                   chunk: int = 1_000) -> pd.DataFrame:
    return _buffer_means(points_df, id_col, covariate_image, COVARIATE_COLS, "covariates", config, chunk)


ROAD_COL = "dist_road_m"
ROAD_SEARCH_M = 50_000


def road_distance_image(year: int | None = None) -> ee.Image:
    roads = ee.FeatureCollection("projects/sat-io/open-datasets/GRIP4/Africa")
    return roads.distance(searchRadius=ROAD_SEARCH_M, maxError=100).unmask(ROAD_SEARCH_M).rename(ROAD_COL)


def add_road_distance(points_df: pd.DataFrame, id_col: str, config: BuffaloConfig = DEFAULT_CONFIG,
                      chunk: int = 1_000) -> pd.DataFrame:
    return _buffer_means(points_df, id_col, road_distance_image, [ROAD_COL], "road distance", config, chunk)


def load_camera_sites(config: BuffaloConfig = DEFAULT_CONFIG) -> pd.DataFrame:
    folder = Path(config.camera_dir)
    consensus = pd.read_csv(folder / "consensus_data.csv",
                            usecols=["SiteID", "LocationX", "LocationY", "Species", "NumVotes", "NumClassifications"])
    effort = pd.read_csv(folder / "search_effort.csv", parse_dates=["Start date", "End date"])

    effort["days"] = (effort["End date"] - effort["Start date"]).dt.days + 1
    trap_days = effort.groupby("Site ID")["days"].sum().rename("trap_days")

    is_buffalo = ((consensus["Species"] == "buffalo")
                  & (consensus["NumVotes"] / consensus["NumClassifications"] >= config.min_agreement))
    captures = consensus[is_buffalo].groupby("SiteID").size().rename("buffalo_captures")

    cam = (consensus.groupby("SiteID")[["LocationX", "LocationY"]].first()
           .join(trap_days).join(captures)
           .fillna({"buffalo_captures": 0})
           .dropna(subset=["trap_days"])
           .reset_index())
    cam = cam[cam["trap_days"] >= config.min_trap_days].reset_index(drop=True)
    cam["rate"] = cam["buffalo_captures"] / cam["trap_days"] * 100

    cam["decimalLongitude"], cam["decimalLatitude"] = to_lonlat.transform(cam["LocationX"].values, cam["LocationY"].values)
    cam["year"] = config.camera_year
    return cam


def camera_species_rate(labels: list, config: BuffaloConfig = DEFAULT_CONFIG) -> pd.Series:
    folder = Path(config.camera_dir)
    photos = pd.read_csv(folder / "consensus_data.csv",
                         usecols=["CaptureEventID", "SiteID", "Species", "NumVotes", "NumClassifications"])
    photos = photos[photos["Species"].isin(labels)]
    events = photos.groupby("CaptureEventID").agg(SiteID=("SiteID", "first"), votes=("NumVotes", "sum"),
                                                   classifications=("NumClassifications", "first"))
    confident = events[(events["votes"] / events["classifications"]).clip(upper=1) >= config.min_agreement]
    captures = confident.groupby("SiteID").size()

    sites = load_camera_sites(config).set_index("SiteID")
    return (captures.reindex(sites.index, fill_value=0) / sites["trap_days"] * 100).rename("rate")


def camera_detection_days(config: BuffaloConfig = DEFAULT_CONFIG) -> pd.Series:
    photos = pd.read_csv(Path(config.camera_dir) / "consensus_data.csv",
                         usecols=["SiteID", "DateTime", "Species", "NumVotes", "NumClassifications"])
    photos = photos[(photos["Species"] == "buffalo")
                    & (photos["NumVotes"] / photos["NumClassifications"] >= config.min_agreement)]
    return photos.assign(day=photos["DateTime"].str[:10]).groupby("SiteID")["day"].nunique().rename("detection_days")


def build_buffalo_dataset(config: BuffaloConfig = DEFAULT_CONFIG) -> BuffaloDataset:
    presences = thin_presences(fetch_buffalo_presences(config), config)
    print("presences after thinning:", len(presences))

    mammals = fetch_mammals(config)
    visited_cells = find_visited_cells(mammals, config)
    print("visited cells:", len(visited_cells))

    points = make_presence_background(presences, config.bounds, visited_cells, config)
    sdm_df = cached(config, "points_embedded", lambda: embed_points(points, "point_id", config))
    print("points missing embeddings:", sdm_df[BAND_COLS].isna().any(axis=1).sum())
    sdm_df = sdm_df.dropna(subset=BAND_COLS).reset_index(drop=True)

    cameras = cached(config, "cameras_embedded", lambda: embed_points(load_camera_sites(config), "SiteID", config))
    cameras = cameras.dropna(subset=BAND_COLS).reset_index(drop=True)

    print(f"dataset: {int(sdm_df['presence'].sum())} presences, {int((sdm_df['presence'] == 0).sum())} background, "
          f"{len(cameras)} cameras")
    return BuffaloDataset(presences, mammals, visited_cells, sdm_df, cameras)
