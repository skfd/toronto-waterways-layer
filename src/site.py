"""Render the GitHub Pages landing page: build/site/index.html.

A self-contained MapLibre GL map that renders the waterways vector tiles
(served alongside it under tiles/vector/) so the Pages root is a live preview of
the layer rather than a bare directory. Values that vary by config are injected
via token replacement to avoid escaping the many braces in the inline CSS/JS.
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
<link href="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.css" rel="stylesheet" />
<script src="https://unpkg.com/maplibre-gl@4.7.1/dist/maplibre-gl.js"></script>
<style>
  html, body { margin: 0; height: 100%; font-family: system-ui, sans-serif; }
  #map { position: absolute; inset: 0; }
  #panel {
    position: absolute; top: 12px; left: 12px; z-index: 1; max-width: 320px;
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
     served as vector tiles.</p>
  <div class="legend"><span class="swatch" style="background:#2b6cb0"></span> River</div>
  <div class="legend"><span class="swatch" style="background:#63b3ed"></span> Creek / Tributary</div>
  <p style="margin-top:10px">Tiles: <code>tiles/vector/{z}/{x}/{y}.pbf</code><br>
     Layer <code>__LAYER__</code>, zoom __MINZOOM__&ndash;__MAXZOOM__.</p>
  <p><a href="https://github.com/__REPO__" target="_blank" rel="noopener">Source &amp; docs on GitHub</a></p>
</div>
<script>
const map = new maplibregl.Map({
  container: 'map',
  center: [-79.37, 43.72],
  zoom: 10,
  attributionControl: { compact: false },
  style: {
    version: 8,
    glyphs: 'https://demotiles.maplibre.org/font/{fontstack}/{range}.pbf',
    sources: {
      waterways: {
        type: 'vector',
        tiles: [location.href.replace(/[^/]*$/, '') + 'tiles/vector/{z}/{x}/{y}.pbf'],
        minzoom: __MINZOOM__,
        maxzoom: __MAXZOOM__,
        attribution: '__ATTRIBUTION__'
      }
    },
    layers: [
      { id: 'bg', type: 'background', paint: { 'background-color': '#eaf0f4' } },
      {
        id: 'waterways-line', type: 'line', source: 'waterways',
        'source-layer': '__LAYER__',
        layout: { 'line-cap': 'round', 'line-join': 'round' },
        paint: {
          'line-color': [
            'match', ['get', 'class'],
            'Creek/Tributary', '#63b3ed',
            '#2b6cb0'
          ],
          'line-width': [
            'interpolate', ['linear'], ['zoom'],
            9, 0.6, 13, 1.6, 16, 3, 19, 6
          ]
        }
      },
      {
        id: 'waterways-label', type: 'symbol', source: 'waterways',
        'source-layer': '__LAYER__', minzoom: 12,
        layout: {
          'symbol-placement': 'line',
          'text-field': ['get', 'name'],
          'text-font': ['Open Sans Regular'],
          'text-size': 12
        },
        paint: {
          'text-color': '#1a4971',
          'text-halo-color': '#ffffff',
          'text-halo-width': 1.4
        }
      }
    ]
  }
});
map.addControl(new maplibregl.NavigationControl(), 'top-right');
map.addControl(new maplibregl.ScaleControl({ unit: 'metric' }));
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
