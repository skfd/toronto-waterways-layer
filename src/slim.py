"""Convert the full TCL centreline GeoJSON into a slim newline-delimited GeoJSON
of watercourses (rivers and creeks).

The source is a single ~88 MB GeoJSON FeatureCollection, so it is parsed as a
stream with ijson -- never loaded into memory at once. This is the inverse of
the streets layer: only features whose FEATURE_CODE_DESC is in
INCLUDE_FEATURE_CODES are kept. Geometry is preserved (LineString /
MultiLineString). Unlike streets, a name is NOT required -- many creek and river
segments are unnamed but still belong on a waterways map; the name is carried as
a label only where present.
"""

import json
import os

import ijson

from src import config

# Sanity bounds for the slimmed feature count. The TCL currently holds ~871
# river + creek segments; the range is wide enough to absorb normal churn but
# tight enough to catch a broken filter (e.g. keeping everything).
MIN_EXPECTED = 600
MAX_EXPECTED = 1_200


def slim(src_path):
    """Stream the big GeoJSON into data/waterways-slim.geojsonl.

    Keeps only features whose FEATURE_CODE_DESC is in INCLUDE_FEATURE_CODES and
    that carry a line geometry. Returns the slim file path. Raises if the
    feature count is implausible.
    """
    print(f"Slimming {src_path} ...")
    os.makedirs(config.DATA_DIR, exist_ok=True)

    count = 0
    skipped = 0
    with open(src_path, "rb") as src, \
            open(config.SLIM_PATH, "w", encoding="utf-8") as out:
        for feature in ijson.items(src, "features.item"):
            props_in = feature.get("properties") or {}
            if props_in.get(config.CLASS_KEY) not in config.INCLUDE_FEATURE_CODES:
                skipped += 1
                continue

            geom = _line_geometry(feature.get("geometry") or {})
            if geom is None:
                skipped += 1
                continue

            props_out = {}
            name = _clean(props_in.get(config.NAME_KEY))
            if name:
                props_out["name"] = name
            klass = _clean(props_in.get(config.CLASS_KEY))
            if klass:
                props_out["class"] = klass
            name_id = props_in.get(config.NAME_ID_KEY)
            if name_id is not None:
                props_out["name_id"] = name_id

            out.write(json.dumps({
                "type": "Feature",
                "geometry": geom,
                "properties": props_out,
            }) + "\n")
            count += 1
            if count % 200 == 0:
                print(f"  {count:,} features ...")

    with open(config.COUNT_PATH, "w", encoding="utf-8") as f:
        f.write(str(count))

    print(f"Done: {config.SLIM_PATH} ({count:,} features, {skipped:,} skipped)")
    if not MIN_EXPECTED <= count <= MAX_EXPECTED:
        raise RuntimeError(
            f"Slim feature count {count:,} is outside the expected range "
            f"{MIN_EXPECTED:,}-{MAX_EXPECTED:,} -- aborting."
        )
    return config.SLIM_PATH


def _clean(val):
    """Strip a source string value, treating the literal 'None' as empty."""
    if val is None:
        return ""
    text = str(val).strip()
    return "" if text in ("", "None") else text


def _line_geometry(geom):
    """Return a LineString/MultiLineString geometry with float coords, or None.

    ijson yields coordinates as Decimal; convert to plain floats (rounded to
    ~0.1 m) so the result is JSON-serializable and compact.
    """
    gtype = geom.get("type")
    coords = geom.get("coordinates")
    if not coords or gtype not in ("LineString", "MultiLineString"):
        return None
    if gtype == "LineString":
        out = _round_line(coords)
    else:
        out = [_round_line(line) for line in coords if line]
        out = [line for line in out if line]
    if not out:
        return None
    return {"type": gtype, "coordinates": out}


def _round_line(line):
    return [[round(float(lon), 6), round(float(lat), 6)] for lon, lat in line]
