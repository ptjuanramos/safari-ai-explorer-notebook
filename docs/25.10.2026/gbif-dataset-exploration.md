# GBIF Dataset Exploration

## What we did

### GBIF occurrences notebook (`animals-sightnings/02_gbif_ocurrences.ipynb`)
- Fixed two broken Plotly cells: `scatter_mapbox` was removed in Plotly 6.x, replaced with `scatter_map` (updated `mapbox_style` → `map_style` accordingly).
- Removed stale `"month": False` hover_data entry that referenced a non-existent column.

### Dataset assessment
Explored the GBIF dataset as a source for wildlife sighting data (cheetah, lion, leopard, elephant, buffalo) within the Tanzania/Serengeti bounding box.

Key conclusion: **GBIF is opportunistic observation data, not a complete survey.** Two main structural problems identified:

- **Sampling bias** — records reflect where tourists and researchers went (mainly along roads), not true animal distribution.
- **Spatial clumping** — multiple observers sighting the same individual animal inflate counts at specific coordinates; low-precision GPS records pile up at center points.

### Path forward
GBIF is not suitable as a training dataset for distribution modeling. Agreed approach:

- Use **IUCN range maps** as the training signal (species presence/likely-presence polygons, independent of tourist routes), combined with existing environmental layers (CHIRPS precipitation, IMERG, road network risk scores).
- Use **GBIF as a held-out validation set** — if a trained model scores high-risk areas where GBIF actually recorded sightings, that's meaningful confirmation without treating coverage gaps as absences.
