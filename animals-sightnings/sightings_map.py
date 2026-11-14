
import json

import folium
import numpy as np
import pandas as pd
from branca.element import JavascriptLink, MacroElement, Template
from scipy.spatial import cKDTree

from buffalo_data import to_utm

PROJ4_JS = "https://cdnjs.cloudflare.com/ajax/libs/proj4js/2.11.0/proj4.js"
UTM_PROJ4 = "+proj=utm +zone=36 +south +datum=WGS84 +units=m +no_defs"

HEAT_STOPS = [(0.0, "#ffffb2"), (0.35, "#fecc5c"), (0.65, "#fd8d3c"), (1.0, "#e31a1c")]


def species_scale_max(records: pd.DataFrame, species_key: int, sigma_m: float = 5_000, min_records: float = 20) -> float:
    xy = records[["x", "y"]].values
    is_species = (records["speciesKey"] == species_key).values.astype(float)
    xs = np.arange(xy[:, 0].min(), xy[:, 0].max(), sigma_m)
    ys = np.arange(xy[:, 1].min(), xy[:, 1].max(), sigma_m)
    centres = np.array([(x, y) for x in xs for y in ys])
    shares = []
    for i, idx in enumerate(cKDTree(xy).query_ball_point(centres, r=3 * sigma_m)):
        if idx:
            w = np.exp(-((xy[idx] - centres[i]) ** 2).sum(axis=1) / (2 * sigma_m ** 2))
            if w.sum() >= min_records:
                shares.append(w @ is_species[idx] / w.sum())
    return float(np.quantile(shares, 0.95))


class SightingsHeat(MacroElement):

    _template = Template("""
    {% macro script(this, kwargs) %}
    (function () {
        var map = {{ this._parent.get_name() }};
        var D = {{ this.data }};
        var CFG = {{ this.settings }};
        var toUTM = proj4("EPSG:4326", CFG.utm);
        var current = 0;

        var canvas = L.DomUtil.create("canvas", "", map.getContainer());
        canvas.style.cssText = "position:absolute;left:0;top:0;pointer-events:none;z-index:450";
        var off = document.createElement("canvas");

        function hexToRgb(h) { return [1, 3, 5].map(function (i) { return parseInt(h.substr(i, 2), 16); }); }
        var stops = CFG.stops.map(function (s) { return [s[0], hexToRgb(s[1])]; });
        function ramp(t) {
            t = Math.max(0, Math.min(1, t));
            for (var i = 1; i < stops.length; i++) {
                if (t <= stops[i][0]) {
                    var a = stops[i - 1], b = stops[i], f = (t - a[0]) / (b[0] - a[0]);
                    return a[1].map(function (v, k) { return v + (b[1][k] - v) * f; });
                }
            }
            return stops[stops.length - 1][1];
        }

        function sigmaMeters() {
            var lat = map.getCenter().lat * Math.PI / 180;
            var metersPerPx = 40075016.686 * Math.cos(lat) / (256 * Math.pow(2, map.getZoom()));
            return Math.max(CFG.min_sigma_m, CFG.kernel_px * metersPerPx);
        }

        function shareAt(ux, uy, sigma, xs, ys, ss) {
            var two_s2 = 2 * sigma * sigma, reach2 = 9 * sigma * sigma, n = 0, k = 0;
            for (var r = 0; r < xs.length; r++) {
                var dx = xs[r] - ux, dy = ys[r] - uy, d2 = dx * dx + dy * dy;
                if (d2 < reach2) {
                    var w = Math.exp(-d2 / two_s2);
                    n += w;
                    if (ss[r] === current) k += w;
                }
            }
            var p0 = D.p0[current];
            return [(k + CFG.prior * p0) / (n + CFG.prior), n, k];
        }

        function recordsNear(sigma) {
            var size = map.getSize(), corners = [[0, 0], [size.x, 0], [0, size.y], [size.x, size.y]].map(function (p) {
                var ll = map.containerPointToLatLng(p); return toUTM.forward([ll.lng, ll.lat]);
            });
            var minx = Math.min.apply(null, corners.map(function (c) { return c[0]; })) - 3 * sigma,
                maxx = Math.max.apply(null, corners.map(function (c) { return c[0]; })) + 3 * sigma,
                miny = Math.min.apply(null, corners.map(function (c) { return c[1]; })) - 3 * sigma,
                maxy = Math.max.apply(null, corners.map(function (c) { return c[1]; })) + 3 * sigma;
            var xs = [], ys = [], ss = [];
            for (var r = 0; r < D.x.length; r++) {
                if (D.x[r] >= minx && D.x[r] <= maxx && D.y[r] >= miny && D.y[r] <= maxy) { xs.push(D.x[r]); ys.push(D.y[r]); ss.push(D.s[r]); }
            }
            return [xs, ys, ss];
        }

        function redraw() {
            var size = map.getSize(), cell = CFG.cell_px;
            canvas.width = size.x; canvas.height = size.y;
            var gw = Math.ceil(size.x / cell) + 1, gh = Math.ceil(size.y / cell) + 1;
            var sigma = sigmaMeters(), near = recordsNear(sigma), vmax = D.vmax[current], p0 = D.p0[current];
            off.width = gw; off.height = gh;
            var octx = off.getContext("2d"), img = octx.createImageData(gw, gh);
            for (var j = 0; j < gh; j++) {
                for (var i = 0; i < gw; i++) {
                    var ll = map.containerPointToLatLng([i * cell, j * cell]), u = toUTM.forward([ll.lng, ll.lat]);
                    var res = shareAt(u[0], u[1], sigma, near[0], near[1], near[2]);
                    var t = (res[0] - p0) / (vmax - p0), o = 4 * (j * gw + i);
                    if (res[1] < CFG.min_records) { img.data[o + 3] = 0; continue; }
                    var c = ramp(t);
                    img.data[o] = c[0]; img.data[o + 1] = c[1]; img.data[o + 2] = c[2];
                    var strength = t < CFG.min_visible ? 0 : Math.pow(Math.min(1, t), 1.5);
                    var confidence = res[1] / (res[1] + CFG.confidence_records);
                    img.data[o + 3] = Math.round(255 * CFG.opacity * strength * confidence);
                }
            }
            octx.putImageData(img, 0, 0);
            var ctx = canvas.getContext("2d");
            ctx.imageSmoothingEnabled = true; ctx.imageSmoothingQuality = "high";
            ctx.drawImage(off, -cell / 2, -cell / 2, gw * cell, gh * cell);
            info.update(sigma);
        }

        var info = L.control({position: "topright"});
        info.onAdd = function () {
            var div = L.DomUtil.create("div");
            div.style.cssText = "background:#fff;padding:8px 10px;border-radius:4px;font:13px/1.45 sans-serif;" +
                "box-shadow:0 1px 4px rgba(0,0,0,.3);max-width:240px";
            L.DomEvent.disableClickPropagation(div);
            var options = D.species.map(function (s, i) { return "<option value='" + i + "'>" + s + "</option>"; }).join("");
            var gradient = CFG.stops.map(function (s) { return s[1] + " " + (100 * s[0]) + "%"; }).join(",");
            div.innerHTML = "<b>Where visitors see</b> <select>" + options + "</select>" +
                "<div style='margin-top:6px'>share of logged animals that were this species</div>" +
                "<div style='height:10px;margin:4px 0;background:linear-gradient(to right," + gradient + ")'></div>" +
                "<div style='display:flex;justify-content:space-between'><span class='p0'></span><span class='vmax'></span></div>" +
                "<div class='scale' style='color:#555;margin-top:4px'></div>" +
                "<div style='color:#555'>No colour: average or below, or too few records to be sure. Click the map for numbers.</div>";
            div.querySelector("select").onchange = function (e) { current = +e.target.value; redraw(); };
            this._div = div;
            return div;
        };
        info.update = function (sigma) {
            this._div.querySelector(".p0").textContent = "average (" + (100 * D.p0[current]).toFixed(1) + "%)";
            this._div.querySelector(".vmax").textContent = Math.round(100 * D.vmax[current]) + "% or more";
            this._div.querySelector(".scale").textContent = "Averaging over about " +
                (sigma >= 1000 ? (sigma / 1000).toFixed(1) + " km" : Math.round(sigma) + " m") + " at this zoom";
        };
        info.addTo(map);

        map.on("click", function (e) {
            var sigma = sigmaMeters(), near = recordsNear(sigma), u = toUTM.forward([e.latlng.lng, e.latlng.lat]);
            var res = shareAt(u[0], u[1], sigma, near[0], near[1], near[2]);
            var n = res[1], p = res[0], half = 1.96 * Math.sqrt(p * (1 - p) / (n + CFG.prior));
            var radius = sigma >= 1000 ? (sigma / 1000).toFixed(1) + " km" : Math.round(sigma) + " m";
            var text = n < CFG.min_records
                ? "Too few animals logged within ~" + radius + " to say (" + n.toFixed(1) + " weighted records)."
                : "Of ~" + Math.round(n) + " animals logged within ~" + radius + ", about <b>" + (100 * p).toFixed(1) + "%</b> were " +
                  D.species[current] + " (range " + Math.max(0, 100 * (p - half)).toFixed(0) + "-" + Math.min(100, 100 * (p + half)).toFixed(0) + "%).";
            L.popup().setLatLng(e.latlng).setContent(text + "<br><span style='color:#777'>" + e.latlng.lat.toFixed(4) + ", " +
                e.latlng.lng.toFixed(4) + "</span>").openOn(map);
        });

        map.on("movestart zoomstart", function () { canvas.style.visibility = "hidden"; });
        map.on("moveend zoomend resize", function () { redraw(); canvas.style.visibility = "visible"; });
        redraw();
    })();
    {% endmacro %}
    """)

    def __init__(self, data: dict, settings: dict):
        super().__init__()
        self._name = "SightingsHeat"
        self.data = json.dumps(data)
        self.settings = json.dumps(settings)


def sightings_heat_map(records: pd.DataFrame, species: dict, bounds, zoom_start: int = 9, location=None,
                       kernel_px: float = 30, cell_px: int = 10, min_sigma_m: float = 250,
                       prior_records: float = 10, min_records: float = 5, confidence_records: float = 10,
                       min_visible: float = 0.15, opacity: float = 0.9) -> folium.Map:
    records = records.dropna(subset=["decimalLongitude", "decimalLatitude"]).copy()
    records["x"], records["y"] = to_utm.transform(records["decimalLongitude"].values, records["decimalLatitude"].values)
    keys = list(species.values())
    code = records["speciesKey"].map({k: i for i, k in enumerate(keys)}).fillna(-1).astype(int)

    data = {
        "species": list(species),
        "x": records["x"].round(0).astype(int).tolist(),
        "y": records["y"].round(0).astype(int).tolist(),
        "s": code.tolist(),
        "p0": [float((records["speciesKey"] == k).mean()) for k in keys],
        "vmax": [species_scale_max(records, k) for k in keys],
    }
    settings = {"utm": UTM_PROJ4, "kernel_px": kernel_px, "cell_px": cell_px, "min_sigma_m": min_sigma_m,
                "prior": prior_records, "min_records": min_records, "confidence_records": confidence_records,
                "min_visible": min_visible, "opacity": opacity, "stops": HEAT_STOPS}

    west, south, east, north = bounds
    m = folium.Map(location=location or [(south + north) / 2, (west + east) / 2], zoom_start=zoom_start,
                   tiles="OpenStreetMap")
    m.get_root().header.add_child(JavascriptLink(PROJ4_JS))
    SightingsHeat(data, settings).add_to(m)
    return m
