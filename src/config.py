"""Configuration constants for the Toronto waterways tile layer build.

Single source of truth. No logic here.

Sibling of toronto-streets-layer: same Toronto Centreline (TCL) source, but the
slim filter is INVERTED -- it keeps only watercourses (rivers and creeks)
instead of streets.
"""

import os

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_DIR, "data")
BUILD_DIR = os.path.join(PROJECT_DIR, "build")
SITE_DIR = os.path.join(BUILD_DIR, "site")

MBTILES_PATH = os.path.join(BUILD_DIR, "waterways.mbtiles")
SLIM_PATH = os.path.join(DATA_DIR, "waterways-slim.geojsonl")
COUNT_PATH = os.path.join(DATA_DIR, "waterways.count")
LAST_DOWNLOAD_PATH = os.path.join(DATA_DIR, ".last-download.json")

VECTOR_TILE_DIR = os.path.join(SITE_DIR, "tiles", "vector")

# Data source: Toronto Centreline (TCL) Version 2, published in WGS84.
# Identical source to the streets layer -- the watercourses live in the same
# file, distinguished by FEATURE_CODE_DESC.
TCL_PACKAGE_ID = "1d079757-377b-4564-82df-eb5638583bfb"
TCL_RESOURCE_ID = "7bc94ccf-7bcf-4a7d-88b1-bdfc8ec5aaf1"
TCL_FILENAME = "centreline-version-2-4326.geojson"
DATASET_URL = (
    f"https://ckan0.cf.opendata.inter.prod-toronto.ca/dataset/"
    f"{TCL_PACKAGE_ID}/resource/{TCL_RESOURCE_ID}/download/{TCL_FILENAME}"
)
DATASET_PAGE = "https://open.toronto.ca/dataset/toronto-centreline-tcl/"
LICENSE_URL = "https://open.toronto.ca/open-data-licence/"
# Plain-ASCII attribution embedded in tile metadata (safe through the WSL shell).
ATTRIBUTION = "(c) City of Toronto, Open Government Licence - Toronto"

# GitHub Pages target. Update both if the repo/account differs.
GITHUB_REPO = "skfd/toronto-waterways-layer"
PAGES_URL = "https://skfd.github.io/toronto-waterways-layer"

# WSL distro that has tippecanoe installed (see the sibling streets layer).
WSL_DISTRO = "Ubuntu"

# Vector tiles. iD requests tiles at (map zoom - 1) and does NOT overzoom, so
# tiles must be generated natively through the zooms used for mapping. Unlike
# the streets layer (z12), waterways start at z9: rivers are large features that
# read well at city-overview zooms.
VECTOR_MINZOOM = 9
VECTOR_MAXZOOM = 19
VECTOR_LAYER_NAME = "waterways"

# TCL FEATURE_CODE_DESC values to KEEP: flowing watercourses only. This is the
# inverse of the streets layer, which excludes these. Shorelines, hydro
# corridors, rail, ferry routes, walkways and actual roads are all dropped.
INCLUDE_FEATURE_CODES = frozenset({
    "River",
    "Creek/Tributary",
})

# Source property keys read from the TCL GeoJSON.
NAME_KEY = "LINEAR_NAME_FULL_LEGAL"   # expanded name, e.g. "Taylor Creek"
CLASS_KEY = "FEATURE_CODE_DESC"       # watercourse class, e.g. "River"
NAME_ID_KEY = "LINEAR_NAME_ID"        # groups segments of one watercourse
