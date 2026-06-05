"""Find Toronto Centreline (TCL) watercourse reaches that OpenStreetMap is missing.

The TCL is the City of Toronto's authoritative centreline; OSM is crowd-sourced.
This module overlays the two and flags every stretch of a TCL river/creek that has
*no* OSM waterway line nearby -- i.e. a reach OSM has not (yet) mapped. The result
is a single GeoJSON in which each TCL reach is split into `covered` / `uncovered`
features, plus a small stats summary used by the published visualisation.

Pipeline position: runs after `slim` (needs data/waterways-slim.geojsonl). The OSM
overlay is fetched once from the Overpass API and cached on disk; pass refresh=True
to re-fetch.

Method: both layers are projected to a local metre grid; OSM lines are densified to
a vertex every COVER_RADIUS metres and indexed in a uniform grid; a TCL vertex is
"covered" if any OSM vertex lies within COVER_RADIUS. A generous radius is used so
positional/digitisation offset between the two datasets is not mistaken for a gap.
"""

import collections
import json
import math
import os
import shutil

from src import config

# A TCL point is "covered" if an OSM waterway line passes within this many metres.
# 40 m comfortably absorbs digitisation offset between the two datasets, so a flagged
# gap means a genuinely absent OSM line rather than a mis-aligned one.
COVER_RADIUS = 40.0

# Sampling step (metres) along TCL lines when testing coverage.
SAMPLE_STEP = 20.0

OSM_CACHE_PATH = os.path.join(config.DATA_DIR, "osm-waterways-geom.json")
GAPS_GEOJSON_PATH = os.path.join(config.DATA_DIR, "osm-gaps.geojson")

# Local equirectangular projection constants around Toronto (~43.7 N).
_LAT0 = 43.7
_M_PER_DEG_LON = 111320 * math.cos(math.radians(_LAT0))
_M_PER_DEG_LAT = 110574


def build_gaps(refresh=False):
    """Compute OSM coverage gaps from the slim TCL data. Returns a stats dict.

    Writes data/osm-gaps.geojson (covered + uncovered reaches). The OSM overlay is
    fetched from Overpass on first use and cached; pass refresh=True to re-fetch.
    """
    if not os.path.isfile(config.SLIM_PATH):
        raise RuntimeError(
            f"Slim GeoJSONL not found: {config.SLIM_PATH}. Run 'slim' first."
        )

    bbox = _bbox(config.SLIM_PATH)
    osm = _load_osm(bbox, refresh=refresh)
    grid = _osm_grid(osm)

    features = []
    cov_m = collections.defaultdict(float)   # name -> covered metres
    unc_m = collections.defaultdict(float)    # name -> uncovered metres
    with open(config.SLIM_PATH, encoding="utf-8") as f:
        for line in f:
            feat = json.loads(line)
            props = feat.get("properties") or {}
            name = props.get("name") or "(unnamed)"
            klass = props.get("class") or ""
            for coords in _segments(feat["geometry"]):
                for covered, run in _split_by_coverage(coords, grid):
                    length = _length_m(run)
                    (cov_m if covered else unc_m)[name] += length
                    if len(run) >= 2:
                        features.append({
                            "type": "Feature",
                            "properties": {
                                "name": name,
                                "class": klass,
                                "covered": covered,
                            },
                            "geometry": {"type": "LineString", "coordinates": run},
                        })

    with open(GAPS_GEOJSON_PATH, "w", encoding="utf-8") as f:
        json.dump({"type": "FeatureCollection", "features": features}, f)

    stats = _summarise(cov_m, unc_m)
    print(
        f"Gaps: {GAPS_GEOJSON_PATH}  "
        f"({stats['uncovered_km']:.1f} of {stats['total_km']:.1f} km missing from OSM, "
        f"{stats['uncovered_pct']:.1f}%)"
    )
    return stats


# --- OSM overlay -----------------------------------------------------------

def _load_osm(bbox, refresh):
    """Return the cached OSM waterway ways (with geometry), fetching if needed."""
    if refresh or not os.path.isfile(OSM_CACHE_PATH):
        _fetch_osm(bbox)
    with open(OSM_CACHE_PATH, encoding="utf-8") as f:
        return json.load(f)


def _fetch_osm(bbox):
    """Download every OSM way tagged `waterway` in bbox to OSM_CACHE_PATH."""
    import requests

    south, west, north, east = bbox
    query = (
        "[out:json][timeout:180];"
        f"(way[waterway]({south:.5f},{west:.5f},{north:.5f},{east:.5f}););"
        "out geom;"
    )
    print("Fetching OSM waterways from Overpass ...")
    resp = requests.post(
        "https://overpass-api.de/api/interpreter",
        data={"data": query},
        headers={"User-Agent": "toronto-waterways-layer/1.0 (osm gap analysis)"},
        timeout=240,
    )
    resp.raise_for_status()
    data = resp.json()
    os.makedirs(config.DATA_DIR, exist_ok=True)
    with open(OSM_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f)
    print(f"  cached {len(data['elements'])} OSM waterway ways -> {OSM_CACHE_PATH}")


def _osm_grid(osm):
    """Index densified OSM vertices into a uniform grid keyed by metre cell."""
    grid = collections.defaultdict(list)

    def add(x, y):
        grid[(int(x // COVER_RADIUS), int(y // COVER_RADIUS))].append((x, y))

    for el in osm.get("elements", []):
        geom = el.get("geometry")
        if not geom:
            continue
        prev = None
        for nd in geom:
            x, y = _xy(nd["lon"], nd["lat"])
            if prev is not None:
                px, py = prev
                d = math.hypot(x - px, y - py)
                for i in range(1, max(1, int(d // COVER_RADIUS))):
                    t = i / max(1, int(d // COVER_RADIUS))
                    add(px + (x - px) * t, py + (y - py) * t)
            add(x, y)
            prev = (x, y)
    return grid


def _covered(x, y, grid):
    """True if any indexed OSM vertex lies within COVER_RADIUS of (x, y)."""
    cx, cy = int(x // COVER_RADIUS), int(y // COVER_RADIUS)
    r2 = COVER_RADIUS * COVER_RADIUS
    for dx in (-1, 0, 1):
        for dy in (-1, 0, 1):
            for px, py in grid.get((cx + dx, cy + dy), ()):
                if (px - x) ** 2 + (py - y) ** 2 <= r2:
                    return True
    return False


# --- TCL line walking ------------------------------------------------------

def _split_by_coverage(coords, grid):
    """Yield (covered_bool, [lon,lat]...) runs, densely resampled along the line.

    The input line is resampled every SAMPLE_STEP metres so a gap is located to
    within one step regardless of the original vertex spacing; consecutive samples
    of the same coverage state are emitted as one run.
    """
    samples = list(_resample(coords))
    if not samples:
        return
    run_state = _covered(*_xy(*samples[0]), grid=grid)
    run = [samples[0]]
    for lon, lat in samples[1:]:
        state = _covered(*_xy(lon, lat), grid=grid)
        if state == run_state:
            run.append([lon, lat])
        else:
            yield run_state, run
            run_state, run = state, [run[-1], [lon, lat]]  # share the boundary point
    yield run_state, run


def _resample(coords):
    """Yield [lon, lat] points spaced ~SAMPLE_STEP metres along the polyline."""
    yield list(coords[0])
    for (x1, y1), (x2, y2) in zip(coords, coords[1:]):
        ax, ay = _xy(x1, y1)
        bx, by = _xy(x2, y2)
        d = math.hypot(bx - ax, by - ay)
        steps = max(1, int(d // SAMPLE_STEP))
        for i in range(1, steps + 1):
            t = i / steps
            yield [x1 + (x2 - x1) * t, y1 + (y2 - y1) * t]


# --- helpers ---------------------------------------------------------------

def _summarise(cov_m, unc_m):
    """Build the stats dict consumed by the visualisation."""
    names = set(cov_m) | set(unc_m)
    per = []
    for name in names:
        cov, unc = cov_m.get(name, 0.0), unc_m.get(name, 0.0)
        total = cov + unc
        per.append({
            "name": name,
            "total_m": round(total),
            "uncovered_m": round(unc),
            "uncovered_pct": round(100 * unc / total, 1) if total else 0.0,
        })
    per.sort(key=lambda r: r["uncovered_m"], reverse=True)
    total_m = sum(cov_m.values()) + sum(unc_m.values())
    unc_total = sum(unc_m.values())
    return {
        "total_km": total_m / 1000,
        "uncovered_km": unc_total / 1000,
        "uncovered_pct": 100 * unc_total / total_m if total_m else 0.0,
        "cover_radius_m": COVER_RADIUS,
        "watercourses": per,
    }


def _segments(geom):
    if geom["type"] == "LineString":
        yield geom["coordinates"]
    else:
        yield from geom["coordinates"]


def _length_m(coords):
    total = 0.0
    for a, b in zip(coords, coords[1:]):
        ax, ay = _xy(*a)
        bx, by = _xy(*b)
        total += math.hypot(bx - ax, by - ay)
    return total


def _bbox(slim_path):
    """Return (south, west, north, east) of all geometry in the slim file."""
    minlon = minlat = 1e9
    maxlon = maxlat = -1e9
    with open(slim_path, encoding="utf-8") as f:
        for line in f:
            for coords in _segments(json.loads(line)["geometry"]):
                for lon, lat in coords:
                    minlon, maxlon = min(minlon, lon), max(maxlon, lon)
                    minlat, maxlat = min(minlat, lat), max(maxlat, lat)
    return minlat, minlon, maxlat, maxlon


def _xy(lon, lat):
    return lon * _M_PER_DEG_LON, lat * _M_PER_DEG_LAT


# --- published visualisation ----------------------------------------------

# Only call out watercourses missing at least this much length in the panel list.
HOTSPOT_MIN_M = 150


def build_gaps_site(refresh=False):
    """Compute gaps and render the published visualisation into build/site/.

    Writes build/site/gaps.html and build/site/osm-gaps.geojson. Returns stats.
    """
    stats = build_gaps(refresh=refresh)
    os.makedirs(config.SITE_DIR, exist_ok=True)
    shutil.copyfile(GAPS_GEOJSON_PATH, os.path.join(config.SITE_DIR, "osm-gaps.geojson"))

    hotspots = _hotspots()
    html = (
        _GAPS_TEMPLATE
        .replace("__MAXZOOM__", str(config.VECTOR_MAXZOOM))
        .replace("__DATASET_PAGE__", config.DATASET_PAGE)
        .replace("__REPO__", config.GITHUB_REPO)
        .replace("__ATTRIBUTION__", config.ATTRIBUTION)
        .replace("__TOTAL_KM__", f"{stats['total_km']:.0f}")
        .replace("__UNCOVERED_KM__", f"{stats['uncovered_km']:.1f}")
        .replace("__UNCOVERED_PCT__", f"{stats['uncovered_pct']:.1f}")
        .replace("__RADIUS__", f"{stats['cover_radius_m']:.0f}")
        .replace("__HOTSPOTS_JSON__", json.dumps(hotspots))
    )
    out_path = os.path.join(config.SITE_DIR, "gaps.html")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"Gaps site: {out_path} ({len(hotspots)} hotspots)")
    return stats


def _hotspots():
    """One fly-to entry per watercourse with a notable gap: name, length, centre.

    The centre is the mean of all that watercourse's uncovered vertices -- close
    enough to drop the viewer onto the missing reaches.
    """
    acc = collections.defaultdict(lambda: [0.0, 0.0, 0])  # name -> [sum_lon, sum_lat, n]
    length = collections.defaultdict(float)
    with open(GAPS_GEOJSON_PATH, encoding="utf-8") as f:
        fc = json.load(f)
    for feat in fc["features"]:
        if feat["properties"]["covered"]:
            continue
        name = feat["properties"]["name"]
        coords = feat["geometry"]["coordinates"]
        length[name] += _length_m(coords)
        for lon, lat in coords:
            acc[name][0] += lon
            acc[name][1] += lat
            acc[name][2] += 1

    rows = []
    for name, (slon, slat, n) in acc.items():
        if length[name] < HOTSPOT_MIN_M or n == 0:
            continue
        rows.append({
            "name": name,
            "m": round(length[name]),
            "lat": round(slat / n, 5),
            "lon": round(slon / n, 5),
        })
    rows.sort(key=lambda r: r["m"], reverse=True)
    return rows


_GAPS_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8" />
<title>Toronto Waterways Missing from OpenStreetMap</title>
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" rel="stylesheet" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>
  html, body { margin: 0; height: 100%; font-family: system-ui, sans-serif; }
  #map { position: absolute; inset: 0; background: #eaf0f4; }
  #panel {
    position: absolute; top: 12px; left: 12px; z-index: 1000; max-width: 330px;
    max-height: calc(100% - 24px); overflow-y: auto;
    background: rgba(255,255,255,0.94); padding: 14px 16px; border-radius: 8px;
    box-shadow: 0 1px 4px rgba(0,0,0,0.25); font-size: 13px; line-height: 1.45;
  }
  #panel h1 { font-size: 16px; margin: 0 0 6px; }
  #panel a { color: #2b6cb0; }
  .stat { font-size: 22px; font-weight: 700; color: #c0392b; }
  .legend { display: flex; align-items: center; gap: 6px; margin: 4px 0; }
  .swatch { width: 22px; height: 4px; border-radius: 2px; flex: none; }
  .hotspots { margin: 8px 0 0; padding: 0; list-style: none; }
  .hotspots li { padding: 3px 0; border-top: 1px solid #eee; }
  .hotspots a { cursor: pointer; text-decoration: none; }
  .hotspots a:hover { text-decoration: underline; }
  .hotspots .len { color: #888; float: right; font-variant-numeric: tabular-nums; }
  .muted { color: #666; font-size: 12px; }
</style>
</head>
<body>
<div id="map"></div>
<div id="panel">
  <h1>Waterways missing from OpenStreetMap</h1>
  <p><span class="stat">__UNCOVERED_KM__ km</span> of Toronto's
     <a href="__DATASET_PAGE__" target="_blank" rel="noopener">Centreline</a>
     rivers and creeks (of __TOTAL_KM__ km, <b>__UNCOVERED_PCT__%</b>) have no OSM
     waterway line within __RADIUS__&nbsp;m &mdash; reaches OSM has not mapped,
     often buried or culverted.</p>
  <div class="legend"><span class="swatch" style="background:#c0392b"></span> Missing from OSM</div>
  <div class="legend"><span class="swatch" style="background:#9fb6c4"></span> Mapped in OSM (context)</div>
  <p class="muted" style="margin:8px 0 2px">Jump to a gap:</p>
  <ul class="hotspots" id="hotspots"></ul>
  <p class="muted" style="margin-top:10px">A reach counts as missing when no OSM
     <code>waterway</code> line of any name passes within __RADIUS__&nbsp;m, so
     mapped-but-offset lines are not flagged. Some gaps are intentionally
     unmapped underground culverts.</p>
  <p class="muted"><a href="index.html">&larr; Back to the waterways map</a> &middot;
     <a href="https://github.com/__REPO__" target="_blank" rel="noopener">Source on GitHub</a></p>
</div>
<script>
const map = L.map('map', { center: [43.77, -79.30], zoom: 12, maxZoom: __MAXZOOM__ });
L.tileLayer('https://tile.openstreetmap.org/{z}/{x}/{y}.png', {
  maxZoom: __MAXZOOM__,
  attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
}).addTo(map);
map.attributionControl.addAttribution('__ATTRIBUTION__');

const COVERED = { color: '#9fb6c4', weight: 1.5, opacity: 0.7 };
const MISSING = { color: '#c0392b', weight: 4, opacity: 0.95 };

fetch('osm-gaps.geojson').then(r => r.json()).then(fc => {
  // Draw covered context first, then missing reaches on top so red stands out.
  const covered = { type: 'FeatureCollection', features: fc.features.filter(f => f.properties.covered) };
  const missing = { type: 'FeatureCollection', features: fc.features.filter(f => !f.properties.covered) };
  L.geoJSON(covered, { style: COVERED, interactive: false }).addTo(map);
  L.geoJSON(missing, {
    style: MISSING,
    onEachFeature: (f, lyr) => lyr.bindPopup(
      '<b>' + f.properties.name + '</b><br>' + (f.properties.class || '') +
      '<br><i>no OSM waterway here</i>')
  }).addTo(map);
});

const hotspots = __HOTSPOTS_JSON__;
const list = document.getElementById('hotspots');
hotspots.forEach(h => {
  const li = document.createElement('li');
  const a = document.createElement('a');
  a.textContent = h.name;
  a.onclick = () => map.flyTo([h.lat, h.lon], 15);
  const span = document.createElement('span');
  span.className = 'len';
  span.textContent = (h.m >= 1000 ? (h.m / 1000).toFixed(1) + ' km' : h.m + ' m');
  li.appendChild(a); li.appendChild(span); list.appendChild(li);
});
</script>
</body>
</html>
"""
