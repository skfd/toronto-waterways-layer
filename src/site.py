"""Render the GitHub Pages landing page: build/site/index.html (+ labels.geojson).

A self-contained map that renders the waterways vector tiles (served alongside
it under tiles/vector/) so the Pages root is a live preview of the layer.

Uses Leaflet + Leaflet.VectorGrid, which draws the MVT tiles to a Canvas (no
WebGL) over an OpenStreetMap raster base. Leaflet.VectorGrid cannot draw
text-along-line, so watercourse names are emitted at build time as a small
labels.geojson (one point per named watercourse, at the midpoint of its longest
segment) and rendered as zoom-gated text markers.

Config-dependent values are injected via token replacement to avoid escaping the
many braces in the inline CSS/JS.
"""

import json
import math
import os

from src import config

# Tokens replaced below. Kept distinct from any CSS/JS braces.
_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Toronto Waterways</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" rel="stylesheet" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<script src="https://unpkg.com/leaflet.vectorgrid@1.3.0/dist/Leaflet.VectorGrid.bundled.js"></script>
<style>
  html, body { margin: 0; height: 100%; font-family: system-ui, sans-serif; }
  #map { position: absolute; inset: 0; background: #eaf0f4; }
  #panel {
    position: absolute; top: 12px; left: 12px; z-index: 1000; max-width: 320px;
    background: rgba(255,255,255,0.92); padding: 14px 16px; border-radius: 8px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.25); font-size: 13px; line-height: 1.45;
  }
  #panel h1 { font-size: 16px; margin: 0 0 6px; }
  #panel a { color: #2b6cb0; }
  #panel code { background: #eef3f6; padding: 1px 4px; border-radius: 3px; font-size: 12px; }
  .legend { display: flex; align-items: center; gap: 6px; margin-top: 4px; }
  .swatch { width: 22px; height: 3px; border-radius: 2px; }
  .wlabel {
    color: #134a73; font-size: 12px; font-weight: 600; white-space: nowrap;
    text-shadow: -1px -1px 1px #fff, 1px -1px 1px #fff, -1px 1px 1px #fff, 1px 1px 1px #fff;
  }
</style>
</head>
<body>
<div id="map"></div>
<div id="panel">
  <h1>Toronto Waterways</h1>
  <p>Rivers and creeks from the
     <a href="__DATASET_PAGE__" target="_blank" rel="noopener">Toronto Centreline</a>,
     served as vector tiles. Click a watercourse for its name.</p>
  <div class="legend"><span class="swatch" style="background:#2b6cb0"></span> River</div>
  <div class="legend"><span class="swatch" style="background:#63b3ed"></span> Creek / Tributary</div>
  <p style="margin-top:10px">Tiles: <code>tiles/vector/{z}/{x}/{y}.pbf</code><br>
     Layer <code>__LAYER__</code>, zoom __MINZOOM__&ndash;__MAXZOOM__.</p>
  <p><a href="gaps.html">See which reaches are missing from OpenStreetMap &rarr;</a></p>
  <p><a href="https://github.com/__REPO__" target="_blank" rel="noopener">Source &amp; docs on GitHub</a></p>
</div>
<script>
const map = L.map('map', { center: [43.72, -79.37], zoom: 11, minZoom: __MINZOOM__, maxZoom: __MAXZOOM__ });

L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: __MAXZOOM__,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);
map.attributionControl.addAttribution('__ATTRIBUTION__');

function style(props, zoom) {
  const creek = props.class === 'Creek/Tributary';
  const weight = zoom < 12 ? 1 : zoom < 15 ? 1.5 : zoom < 17 ? 2.5 : 4;
  return { color: creek ? '#63b3ed' : '#2b6cb0', weight: weight, opacity: 0.9 };
}

const layer = L.vectorGrid.protobuf('tiles/vector/{z}/{x}/{y}.pbf', {
  rendererFactory: L.canvas.tile,
  minZoom: __MINZOOM__,
  maxZoom: __MAXZOOM__,
  maxNativeZoom: __MAXZOOM__,
  interactive: true,
  vectorTileLayerStyles: { '__LAYER__': style }
}).addTo(map);

layer.on('click', function (e) {
  const p = e.layer.properties || {};
  const name = p.name || '(unnamed watercourse)';
  L.popup().setLatLng(e.latlng)
    .setContent('<b>' + name + '</b><br>' + (p.class || ''))
    .openOn(map);
});

// Name labels: a small point layer, shown only when zoomed in enough.
const labels = L.layerGroup();
const LABEL_MIN_ZOOM = 12;
fetch('labels.geojson').then(r => r.json()).then(fc => {
  L.geoJSON(fc, {
    pointToLayer: (f, latlng) => L.marker(latlng, {
      interactive: false,
      icon: L.divIcon({ className: 'wlabel', html: f.properties.name, iconSize: null })
    })
  }).addTo(labels);
  updateLabels();
});
function updateLabels() {
  if (map.getZoom() >= LABEL_MIN_ZOOM) { if (!map.hasLayer(labels)) labels.addTo(map); }
  else if (map.hasLayer(labels)) { map.removeLayer(labels); }
}
map.on('zoomend', updateLabels);
</script>
</body>
</html>
"""


def build_site():
    """Write build/site/index.html and build/site/labels.geojson. Returns the html path."""
    os.makedirs(config.SITE_DIR, exist_ok=True)
    _write_labels()

    html = (
        _TEMPLATE
        .replace("__LAYER__", config.VECTOR_LAYER_NAME)
        .replace("__MINZOOM__", str(config.VECTOR_MINZOOM))
        .replace("__MAXZOOM__", str(config.VECTOR_MAXZOOM))
        .replace("__ATTRIBUTION__", config.ATTRIBUTION)
        .replace("__DATASET_PAGE__", config.DATASET_PAGE)
        .replace("__REPO__", config.GITHUB_REPO)
    )
    out_path = os.path.join(config.SITE_DIR, "index.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Site: {out_path}")
    return out_path


def _write_labels():
    """Emit one label point per named watercourse from the slim GeoJSONL.

    Each watercourse's label sits at the midpoint of its longest single segment,
    a stable, on-the-line spot. Written to build/site/labels.geojson.
    """
    if not os.path.isfile(config.SLIM_PATH):
        raise RuntimeError(
            f"Slim GeoJSONL not found: {config.SLIM_PATH}. Run 'slim' first."
        )

    best = {}  # name -> (length, midpoint [lon, lat])
    with open(config.SLIM_PATH, encoding="utf-8") as f:
        for line in f:
            feat = json.loads(line)
            name = (feat.get("properties") or {}).get("name")
            if not name:
                continue
            for seg in _segments(feat["geometry"]):
                length, mid = _line_length_midpoint(seg)
                if name not in best or length > best[name][0]:
                    best[name] = (length, mid)

    features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": mid},
            "properties": {"name": name},
        }
        for name, (_, mid) in sorted(best.items())
    ]
    out_path = os.path.join(config.SITE_DIR, "labels.geojson")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f)
    print(f"Labels: {out_path} ({len(features)} named watercourses)")


def _segments(geom):
    """Yield each coordinate list (one LineString) from a (Multi)LineString."""
    if geom["type"] == "LineString":
        yield geom["coordinates"]
    else:
        yield from geom["coordinates"]


def _line_length_midpoint(coords):
    """Return (length, [lon, lat]) where the point is halfway along the line.

    Length is an approximate planar metric in metres (good enough to compare
    segments of the same watercourse). The midpoint is interpolated at half the
    cumulative length, so the label lands on the line rather than at a vertex.
    """
    cos_lat = math.cos(math.radians(coords[0][1]))
    dists = []
    total = 0.0
    for (x1, y1), (x2, y2) in zip(coords, coords[1:]):
        dx = (x2 - x1) * 111320 * cos_lat
        dy = (y2 - y1) * 110540
        d = math.hypot(dx, dy)
        dists.append(d)
        total += d
    if total == 0:
        return 0.0, list(coords[0])

    half = total / 2
    run = 0.0
    for (p1, p2), d in zip(zip(coords, coords[1:]), dists):
        if run + d >= half:
            t = (half - run) / d if d else 0
            return total, [p1[0] + (p2[0] - p1[0]) * t, p1[1] + (p2[1] - p1[1]) * t]
        run += d
    return total, list(coords[-1])
