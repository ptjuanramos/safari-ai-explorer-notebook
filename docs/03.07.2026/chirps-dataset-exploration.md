# CHIRPS Dataset Exploration

## What we did

### EDA notebook (`eda/01_obtain_chrips.ipynb`)
- Authenticated with Google Earth Engine and fetched the first batch of CHIRPS daily imagery for the Serengeti/Tanzania bounding box (`34.00, -4.50 → 37.00, -1.50`).
- Confirmed date coverage for a sample November 2023 window (29/30 days present; 2023-11-30 was the missing day due to the dataset's ~2–3 week publication lag).
- Visualised the collection as a video thumbnail to get a first look at spatial rainfall patterns over the park.

### Dataset assessment

CHIRPS (Climate Hazards Group InfraRed Precipitation with Station data) is a satellite-derived daily rainfall product blended with ground station observations.

Key properties:

- **Spatial resolution:** 0.05° per pixel (~5 km at the equator).
- **Temporal resolution:** daily.
- **Period:** 1981 – near-present (2–3 week publication delay).
- **Coverage:** global tropics and sub-tropics, including Tanzania/Serengeti.

Key conclusion: **CHIRPS is suitable as a rainfall risk signal, but its latency rules it out for live dispatch.** It is used here to build and calibrate the rainfall→risk relationship and to provide a seasonal/historical risk prior. If a real-time feature is ever needed, CHIRPS would be swapped for GPM IMERG (~4 h latency) behind the same interface.

### CHIRPS pixel grid vs OSM edges

Explored how many OSM road edges fall inside a single CHIRPS pixel to understand the mapping cardinality before building the risk join.

Findings for Tarangire National Park:

- CHIRPS pixels covering the park bbox: **180**
- Road edges in the park graph: **2 439**
- Pixels with at least one edge: **93** (mean 30 edges/pixel, max 542)
- **`number_edges > number_pixels` confirmed** — many edges share one rainfall reading.

This shapes the integration: each edge inherits the risk of the CHIRPS pixel it spatially intersects (`predicate="intersects"` join), rather than expecting a 1:1 mapping.

### Rain risk thresholds and road vulnerability

Chose a threshold table to convert accumulated rainfall (mm) into a 0–1 risk score:

| Accumulated rain | Risk score |
|-----------------|-----------|
| < 5 mm | 0.0 |
| 5 – 15 mm | 0.3 |
| 15 – 30 mm | 0.6 |
| ≥ 30 mm | 1.0 |

Road type vulnerability multipliers scale this further (paved roads barely affected, dirt tracks heavily), combined with a base road-type risk:

```
surface_risk = min(1.0, base_road_risk + vulnerability[road_type] * rain_risk)
```

These are reasoned starting estimates — they need validation against real road-condition reports once available.

### Rolling accumulation window

A single day of light rain rarely makes a track impassable; consecutive wet days do, because the ground stays saturated. Decision: **rolling 3-day accumulated precipitation** (current day + two prior days) as the rainfall signal, recomputed per pixel per day. Three days is a starting point that can be tuned once real road-condition feedback exists.

### Note: why lat/lon degrees were converted to meters

When calling `reduceRegions` on Google Earth Engine, the `scale` parameter controls the sampling resolution and **must be expressed in meters** — it is the pixel size used to resample the image before aggregating over each region. CHIRPS pixels are 0.05° wide; at the equator, 1° ≈ 111 320 m, so:

```
0.05° × 111 320 m/° ≈ 5 566 m
```

Passing `scale=5566` tells Earth Engine to sample at roughly the native CHIRPS resolution, so the `mean` reducer over each pixel polygon returns a value representative of that pixel and not an artificially smoothed or aliased one. Using degrees directly (e.g. `scale=0.05`) would raise an error because EE's scale is always in the projection's native unit, which for the default Web Mercator export is meters.
