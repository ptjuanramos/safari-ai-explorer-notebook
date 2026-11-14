
import ee
import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree
from scipy.stats import spearmanr
from shapely.geometry import box
from shapely.ops import unary_union
from sklearn.cluster import KMeans
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score, roc_curve
from sklearn.model_selection import GroupKFold, StratifiedGroupKFold
from xgboost import XGBClassifier

from buffalo_data import BAND_COLS, UTM, to_utm

XGB_SETTINGS = {
    "default": {},
    "regularized": dict(max_depth=3, learning_rate=0.05, n_estimators=300, min_child_weight=5,
                        subsample=0.8, colsample_bytree=0.8, reg_lambda=5.0),
    "strongly regularized": dict(max_depth=2, learning_rate=0.03, n_estimators=400, min_child_weight=20,
                                 subsample=0.7, colsample_bytree=0.5, reg_lambda=20.0),
}

PROTECTED_AREAS = {
    916: "Serengeti NP",
    555623796: "Ngorongoro CA",
    924: "Lake Manyara NP",
    7437: "Maswa GR",
    31595: "Grumeti GR",
    32811: "Ikorongo GR",
    352222: "Ikona WMA",
    555623786: "Loliondo GCA",
    555623785: "Lake Natron GCA",
    555623781: "Mto wa Mbu GCA",
    1297: "Masai Mara NR",
}
OUTSIDE = "outside protected areas"

SERENGETI_AREAS = ["Serengeti NP", "Grumeti GR", "Ikorongo GR", "Ikona WMA", "Maswa GR", "Loliondo GCA", "Masai Mara NR"]
HIGHLAND_AREAS = ["Ngorongoro CA", "Lake Manyara NP", "Mto wa Mbu GCA"]


def year_matched(df: pd.DataFrame, max_ratio: int = 10, seed: int = 42) -> tuple[pd.DataFrame, int]:
    presences = df[df["presence"] == 1]
    background = df[df["presence"] == 0]
    n_presences = presences.groupby("year").size()
    available = background.groupby("year").size().reindex(n_presences.index, fill_value=0)
    ratio = int(min(max_ratio, (available // n_presences).min()))
    parts = [presences] + [background[background["year"] == year].sample(n * ratio, random_state=seed)
                           for year, n in n_presences.items()]
    return pd.concat(parts).reset_index(drop=True), ratio


def make_model(y: pd.Series, params: dict | None = None) -> XGBClassifier:
    return XGBClassifier(scale_pos_weight=(y == 0).sum() / (y == 1).sum(), eval_metric="auc",
                         random_state=42, n_jobs=-1, **(params or {}))


def best_tss_threshold(y_true, score) -> float:
    fpr, tpr, thresholds = roc_curve(y_true, score)
    return thresholds[np.argmax(tpr - fpr)]


def tss(y_true, score, threshold) -> float:
    predicted = score >= threshold
    return predicted[y_true == 1].mean() + (~predicted[y_true == 0]).mean() - 1


def calibration_slope(y_true, score) -> float:
    s = np.clip(np.asarray(score), 1e-4, 1 - 1e-4)
    logit = np.log(s / (1 - s)).reshape(-1, 1)
    return LogisticRegression(C=np.inf).fit(logit, y_true).coef_[0, 0]


def camera_agreement(cam: pd.DataFrame, score) -> dict:
    rho, p_value = spearmanr(score, cam["rate"])
    groups = pd.qcut(score, 3, labels=["low", "medium", "high"])
    medians = cam["rate"].groupby(groups, observed=True).median()
    return {"camera rho": rho, "camera p": p_value,
            "median rate low": medians["low"], "median rate medium": medians["medium"], "median rate high": medians["high"]}


def add_utm(df: pd.DataFrame, cell_size_m: int) -> pd.DataFrame:
    df = df.copy()
    df["x"], df["y"] = to_utm.transform(df["decimalLongitude"].values, df["decimalLatitude"].values)
    df["cell"] = (df["x"] // cell_size_m).astype(int).astype(str) + "_" + (df["y"] // cell_size_m).astype(int).astype(str)
    return df


def presence_regions(df: pd.DataFrame, k: int, seed: int = 42) -> np.ndarray:
    presences = df.loc[df["presence"] == 1, ["x", "y"]].values
    return KMeans(n_clusters=k, n_init=10, random_state=seed).fit(presences).cluster_centers_


def nearest_region(df: pd.DataFrame, centres: np.ndarray) -> np.ndarray:
    distances = np.hypot(df["x"].values[:, None] - centres[:, 0], df["y"].values[:, None] - centres[:, 1])
    return np.array([f"region {i}" for i in distances.argmin(axis=1)])


def fetch_protected_areas() -> gpd.GeoDataFrame:
    fc = (ee.FeatureCollection("WCMC/WDPA/current/polygons")
          .filter(ee.Filter.inList("SITE_ID", list(PROTECTED_AREAS)))
          .map(lambda f: f.simplify(maxError=100)))
    areas = gpd.GeoDataFrame.from_features(fc.getInfo()["features"], crs="EPSG:4326")
    areas["area"] = areas["SITE_ID"].map(PROTECTED_AREAS)
    areas["order"] = areas["SITE_ID"].map({site: i for i, site in enumerate(PROTECTED_AREAS)})
    return areas.sort_values("order")[["area", "geometry"]].to_crs(UTM).reset_index(drop=True)


def protected_area_of(df: pd.DataFrame, areas: gpd.GeoDataFrame) -> pd.Series:
    points = gpd.GeoDataFrame(geometry=gpd.points_from_xy(df["x"], df["y"]), crs=UTM, index=df.index)
    hits = gpd.sjoin(points, areas, predicate="within", how="left")
    hits["rank"] = hits["area"].map({name: i for i, name in enumerate(PROTECTED_AREAS.values())})
    first = hits.sort_values("rank").groupby(level=0)["area"].first()
    return first.reindex(df.index).fillna(OUTSIDE)


class FixedAtPrediction:

    def __init__(self, model, values: dict):
        self.model, self.values = model, values

    def predict_proba(self, X: pd.DataFrame):
        return self.model.predict_proba(X.assign(**self.values))


def _fit(X_train, y_train, y_all, params, fixed_at_prediction):
    model = make_model(y_all, params).fit(X_train, y_train)
    if fixed_at_prediction:
        model = FixedAtPrediction(model, {c: X_train[c].median() for c in fixed_at_prediction})
    return model


def blocked_cv(df: pd.DataFrame, splits, fold_names, params: dict | None = None, features: list = BAND_COLS,
               fixed_at_prediction: list | None = None):
    X, y = df[features], df["presence"]
    rows, held_out, models = [], pd.Series(index=df.index, dtype=float), {}
    for (train, test), name in zip(splits, fold_names):
        X_train, y_train = X.iloc[train], y.iloc[train]
        inner = np.empty(len(train))
        for inner_train, inner_test in GroupKFold(n_splits=3).split(X_train, y_train, groups=df["cell"].iloc[train]):
            inner_model = _fit(X_train.iloc[inner_train], y_train.iloc[inner_train], y, params, fixed_at_prediction)
            inner[inner_test] = inner_model.predict_proba(X_train.iloc[inner_test])[:, 1]
        threshold = best_tss_threshold(y_train.values, inner)

        model = _fit(X_train, y_train, y, params, fixed_at_prediction)
        score = model.predict_proba(X.iloc[test])[:, 1]
        y_test = y.iloc[test].values
        held_out.iloc[test] = score
        models[name] = model
        rows.append({"held out": name, "presences": y_test.sum(), "background": (y_test == 0).sum(),
                     "AUC": roc_auc_score(y_test, score), "TSS": tss(y_test, score, threshold),
                     "cut-off": threshold, "Brier": brier_score_loss(y_test, score)})
    table = pd.DataFrame(rows).set_index("held out").astype(float)
    table.loc["mean"] = table.mean()
    return table.round(3), held_out, models


def region_evaluation(df: pd.DataFrame, cam: pd.DataFrame, k: int, params: dict | None = None,
                      features: list = BAND_COLS, fixed_at_prediction: list | None = None):
    centres = presence_regions(df, k)
    df = df.assign(region=nearest_region(df, centres))
    X, y = df[features], df["presence"]

    block_splits = list(StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=42).split(X, y, groups=df["cell"]))
    block_table, _, _ = blocked_cv(df, block_splits, [f"fold {i}" for i in range(5)], params, features, fixed_at_prediction)

    region_names = sorted(df["region"].unique())
    region_splits = [(np.where(df["region"] != r)[0], np.where(df["region"] == r)[0]) for r in region_names]
    region_table, region_scores, region_models = blocked_cv(df, region_splits, region_names, params, features,
                                                            fixed_at_prediction)

    cam_region = nearest_region(cam, centres)
    cam_score = pd.Series(index=cam.index, dtype=float)
    for region in np.unique(cam_region):
        inside = cam_region == region
        cam_score[inside] = region_models[region].predict_proba(cam.loc[inside, features])[:, 1]

    summary = {"block AUC": block_table.loc["mean", "AUC"], "region AUC": region_table.loc["mean", "AUC"],
               "region TSS": region_table.loc["mean", "TSS"], "calibration slope": calibration_slope(y, region_scores),
               **camera_agreement(cam, cam_score)}
    return summary, region_table


def serengeti_map_grid(visited_cells: set, areas: gpd.GeoDataFrame, config, year: int, spacing_m: int,
                       chunk: int = 1_000) -> pd.DataFrame:
    import buffalo_data as bd

    size = config.cell_size_m
    offsets = np.arange(spacing_m / 2, size, spacing_m)
    grid = pd.DataFrame([(cx * size + ox, cy * size + oy) for cx, cy in visited_cells for ox in offsets for oy in offsets],
                        columns=["x", "y"])
    grid["decimalLongitude"], grid["decimalLatitude"] = bd.to_lonlat.transform(grid["x"].values, grid["y"].values)
    west, south, east, north = config.bounds
    in_box = grid["decimalLongitude"].between(west, east) & grid["decimalLatitude"].between(south, north)
    grid = grid[in_box & protected_area_of(grid, areas).isin(SERENGETI_AREAS)].reset_index(drop=True)
    grid["point_id"] = "grid_" + grid.index.astype(str)
    grid["year"] = year
    print("grid points:", len(grid))
    grid = pd.concat([bd.embed_points(grid.iloc[s:s + chunk], "point_id", config) for s in range(0, len(grid), chunk)],
                     ignore_index=True)
    return bd.add_covariates(grid, "point_id", config)


SAFARI_SPECIES = {
    "buffalo": {"speciesKey": 2441034, "camera_labels": ["buffalo"]},
    "elephant": {"speciesKey": 2435350, "camera_labels": ["elephant"]},
    "lion": {"speciesKey": 5219404, "camera_labels": ["lionFemale", "lionMale"]},
    "cheetah": {"speciesKey": 2435270, "camera_labels": ["cheetah"]},
    "leopard": {"speciesKey": 5219436, "camera_labels": ["leopard"]},
}


def serengeti_presences(records: pd.DataFrame, species_key: int, areas: gpd.GeoDataFrame, config) -> pd.DataFrame:
    import buffalo_data as bd

    sightings = add_utm(records[records["speciesKey"] == species_key], config.cell_size_m)
    sightings = sightings[protected_area_of(sightings, areas).isin(SERENGETI_AREAS)]
    return bd.thin_presences(sightings, config)[["gbifID", "decimalLongitude", "decimalLatitude", "year"]]


def serengeti_background_pool(n_per_year: dict, visited_cells: set, areas: gpd.GeoDataFrame, config) -> pd.DataFrame:
    import buffalo_data as bd
    from shapely import contains_xy
    from shapely.ops import unary_union

    rng = np.random.default_rng(config.seed)
    serengeti = unary_union(areas[areas["area"].isin(SERENGETI_AREAS)].geometry)
    cells = np.array(sorted(visited_cells))
    west, south, east, north = config.bounds
    rows = []
    for year, n in sorted(n_per_year.items()):
        kept = np.empty((0, 2))
        while len(kept) < n:
            pick = cells[rng.integers(len(cells), size=4 * n)]
            xy = (pick + rng.uniform(size=(4 * n, 2))) * config.cell_size_m
            lon, lat = bd.to_lonlat.transform(xy[:, 0], xy[:, 1])
            ok = contains_xy(serengeti, xy[:, 0], xy[:, 1]) & (lon >= west) & (lon <= east) & (lat >= south) & (lat <= north)
            kept = np.vstack([kept, xy[ok]])
        kept = kept[:n]
        lon, lat = bd.to_lonlat.transform(kept[:, 0], kept[:, 1])
        rows.append(pd.DataFrame({"decimalLongitude": lon, "decimalLatitude": lat, "year": float(year)}))
    pool = pd.concat(rows, ignore_index=True)
    pool.insert(0, "point_id", [f"pool_{i}" for i in range(len(pool))])
    return pool


def species_dataset(presences: pd.DataFrame, pool: pd.DataFrame, config, max_ratio: int = 10) -> tuple[pd.DataFrame, int]:
    presences = add_utm(presences.assign(presence=1), config.cell_size_m)
    pool = add_utm(pool.assign(presence=0), config.cell_size_m)
    keep = np.ones(len(pool), dtype=bool)
    for year, group in presences.groupby("year"):
        same_year = (pool["year"] == year).values
        distance = cKDTree(group[["x", "y"]].values).query(pool.loc[same_year, ["x", "y"]].values)[0]
        keep[np.where(same_year)[0][distance < config.buffer_m]] = False
    return year_matched(pd.concat([presences, pool[keep]], ignore_index=True), max_ratio)


def hotspot_areas(grid: pd.DataFrame, score, cameras: pd.DataFrame, spacing_m: int, smooth_sigma_m: float = 3_000,
                  hot_percent: float = 10, peak_radius_m: float = 4_000, n_areas: int = 3) -> gpd.GeoDataFrame:
    grid = grid.assign(percentile=pd.Series(score, index=grid.index).rank(pct=True) * 100)
    xy, pct = grid[["x", "y"]].values, grid["percentile"].values
    neighbours = cKDTree(xy).query_ball_point(xy, r=3 * smooth_sigma_m)
    weights = [np.exp(-((xy[idx] - xy[i]) ** 2).sum(axis=1) / (2 * smooth_sigma_m ** 2)) for i, idx in enumerate(neighbours)]
    grid["smoothed"] = [(w * pct[idx]).sum() / w.sum() for w, idx in zip(weights, neighbours)]

    remaining = grid[grid["smoothed"] >= grid["smoothed"].quantile(1 - hot_percent / 100)]
    picked = []
    while len(picked) < n_areas and len(remaining):
        peak = remaining.loc[remaining["smoothed"].idxmax()]
        members = remaining[np.hypot(remaining["x"] - peak["x"], remaining["y"] - peak["y"]) <= peak_radius_m]
        picked.append((peak, members))
        remaining = remaining.drop(members.index)

    half = spacing_m / 2
    areas_table = gpd.GeoDataFrame([
        {"rank": rank, "area_km2": len(members) * (spacing_m / 1000) ** 2, "percentile": members["percentile"].mean(),
         "peak_lon": peak["decimalLongitude"], "peak_lat": peak["decimalLatitude"],
         "geometry": unary_union([box(x - half, y - half, x + half, y + half) for x, y in members[["x", "y"]].values])}
        for rank, (peak, members) in enumerate(picked, start=1)
    ], geometry="geometry", crs=UTM)
    cams = gpd.GeoDataFrame(cameras[["rate"]], geometry=gpd.points_from_xy(cameras["x"], cameras["y"]), crs=UTM)
    inside = gpd.sjoin(cams, areas_table[["rank", "geometry"]], predicate="within")
    areas_table["cameras"] = areas_table["rank"].map(inside.groupby("rank").size()).fillna(0).astype(int)
    areas_table["camera median rate"] = areas_table["rank"].map(inside.groupby("rank")["rate"].median())
    return areas_table.to_crs("EPSG:4326")
