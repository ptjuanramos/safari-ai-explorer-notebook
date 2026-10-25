# ADR-0001: Always use a metric coordinate system (UTM / meters)

**Date:** 25.10.2026  
**Status:** Accepted

## Context

The project mixes several spatial data sources — OSMnx road graphs, CHIRPS rainfall pixels, IUCN range polygons, IMERG tiles — each of which can be delivered in geographic coordinates (EPSG:4326, degrees lat/lon). Operating directly in degrees causes two recurring problems:

1. **Distance / area calculations are wrong.** A degree of longitude near the equator is ~111 km but shrinks towards the poles; arithmetic on raw degree values produces distorted lengths, areas, and buffers.
2. **Tool APIs expect meters.** Google Earth Engine's `scale` parameter, Shapely buffer radii, and OSMnx's `length` output all work in meters. Mixing units forces ad-hoc conversion at every call site (the `5 566 m` workaround in `chirps_provider.py` is a symptom of this).

## Decision

All spatial data **must be projected to a metric CRS before any geometric operation**. For the Tanzania/Serengeti area the standard choice is:

- **EPSG:32736** — WGS 84 / UTM zone 36S (covers the park and surrounding bbox)

Data may be stored or exchanged in EPSG:4326 (e.g. GEE inputs, OSMnx output), but must be reprojected with `.to_crs("EPSG:32736")` before any distance, area, buffer, or spatial-join operation. Results can be reprojected back to 4326 for display if needed.

## Consequences

- All GeoDataFrame operations use `.to_crs("EPSG:32736")` before geometric work; reprojected frames are never stored as the canonical source.
- The `5 566 m` magic number in `CHIRPSProvider.get_accumulated_precipitation` becomes derivable from the grid geometry once the frame is in meters, and can eventually be replaced with `pixel_grid.geometry[0].length / 4` or equivalent.
- Buffers, distance thresholds, and radius parameters across the codebase are documented and specified in **meters**, not degrees.
- New data sources must declare which CRS they arrive in and add a reprojection step before any join or calculation.
