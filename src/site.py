"""Render the GitHub Pages landing page: build/site/index.html.

A self-contained map that renders the waterways vector tiles (served alongside
it under tiles/vector/) so the Pages root is a live preview of the layer rather
than a bare directory.

Uses Leaflet + Leaflet.VectorGrid, which draws the MVT tiles to a Canvas (no
WebGL). This works on browsers/machines where WebGL is unavailable, unlike
MapLibre GL. Config-dependent values are injected via token replacement to avoid
escaping the many braces in the inline CSS/JS.
"""

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
  <p><a href="https://github.com/__REPO__" target="_blank" rel="noopener">Source &amp; docs on GitHub</a></p>
</div>
<script>
const map = L.map('map', { center: [43.72, -79.37], zoom: 11, minZoom: __MINZOOM__, maxZoom: __MAXZOOM__ });
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
</script>
</body>
</html>
"""


def build_site():
    """Write build/site/index.html. Returns its path."""
    os.makedirs(config.SITE_DIR, exist_ok=True)
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
