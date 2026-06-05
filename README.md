# Toronto Waterways Tile Layer

Vector (MVT) tiles of Toronto's **rivers and creeks**, built from the
[Toronto Centreline (TCL)](https://open.toronto.ca/dataset/toronto-centreline-tcl/)
open dataset and served as a slippy-map tile pyramid on GitHub Pages.

**Live tiles:** https://skfd.github.io/toronto-waterways-layer/

This is a sibling of [`toronto-streets-layer`](https://github.com/skfd/toronto-streets-layer):
same source file and the same `tippecanoe`-in-WSL pipeline, but the slim filter is
*inverted* — instead of excluding watercourses, it keeps **only** features whose
`FEATURE_CODE_DESC` is `River` or `Creek/Tributary`. Everything else (roads,
shorelines, rail, hydro corridors, walkways) is dropped.

## Tile endpoint

```
https://skfd.github.io/toronto-waterways-layer/tiles/vector/{z}/{x}/{y}.pbf
```

| | |
|---|---|
| Layer name | `waterways` |
| Zoom range | z9 – z19 (native, no overzoom) |
| Geometry | `LineString` / `MultiLineString` |
| Features | 871 segments (746 river + 125 creek) |

Each feature carries:

| Property | Example | Notes |
|---|---|---|
| `name` | `Taylor Creek` | absent on unnamed segments |
| `class` | `River` or `Creek/Tributary` | TCL `FEATURE_CODE_DESC` |
| `name_id` | `12345` | groups segments of one watercourse |

Rivers start at z9 (city-overview) because they are large features; short creeks
are simplified at low zoom but never dropped.

## Build pipeline

```
download  ->  slim  ->  vector  ->  site  ->  publish
```

1. **download** — fetch the latest TCL centreline GeoJSON from the Toronto Open
   Data portal. Smart-cached: a HEAD request compares `Last-Modified` +
   `Content-Length` against a sidecar and only re-fetches on change.
2. **slim** — stream the ~88 MB GeoJSON with `ijson` (never loaded whole),
   keeping only watercourses, and write a compact newline-delimited GeoJSON.
3. **vector** — drive `tippecanoe` + `tile-join` inside WSL to produce the
   `{z}/{x}/{y}.pbf` pyramid.
4. **site** — render `build/site/index.html`, a self-contained MapLibre map that
   previews the tiles.
5. **publish** — force-push `build/site/` as a single orphan commit to the
   `gh-pages` branch (history never grows).

## Usage

```powershell
pip install -r requirements.txt

python run.py download   # fetch the TCL centreline GeoJSON
python run.py slim       # filter to watercourses -> data/waterways-slim.geojsonl
python run.py vector     # build MVT tiles via WSL tippecanoe
python run.py site       # render build/site/index.html (map preview)
python run.py build      # download + slim + vector + site
python run.py publish    # force-push tiles to the gh-pages branch
python run.py update     # build + publish (daily scheduled-task entry point)
```

### Requirements

- Python 3 with `requests` and `ijson` (`requirements.txt`).
- [`tippecanoe`](https://github.com/felt/tippecanoe) installed inside WSL — it
  does not run natively on Windows. Set the distro name in
  [`src/config.py`](src/config.py) (`WSL_DISTRO`, default `Ubuntu`).
- A GitHub repo with an `origin` remote for `publish`.

## Configuration

All knobs live in [`src/config.py`](src/config.py): the dataset URL, the
`INCLUDE_FEATURE_CODES` filter, zoom range, layer name, and the GitHub
repo/Pages target.

## Data source & licence

Data: City of Toronto — Toronto Centreline (TCL), published in WGS84.
Used under the [Open Government Licence – Toronto](https://open.toronto.ca/open-data-licence/).

> (c) City of Toronto, Open Government Licence – Toronto
