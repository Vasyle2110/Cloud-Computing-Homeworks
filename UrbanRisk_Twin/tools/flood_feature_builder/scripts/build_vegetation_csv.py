import csv
import math
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np
import requests
from dotenv import load_dotenv
from pyproj import Transformer
from shapely.geometry import Point, Polygon
from shapely.ops import transform, unary_union


try:
    import rasterio
    from rasterio.io import MemoryFile
except ImportError:
    rasterio = None
    MemoryFile = None


try:
    import ee
except ImportError:
    ee = None


# ============================================================
# Paths
# ============================================================

SCRIPT_PATH = Path(__file__).resolve()

# build_vegetation_csv.py
# scripts/
# flood_feature_builder/
# tools/
# UrbanRisk_Twin/
BUILDER_ROOT = SCRIPT_PATH.parents[1]
BUILDER_DATA_DIR = BUILDER_ROOT / "data"
OUTPUT_FILE = BUILDER_DATA_DIR / "vegetation_features.csv"

ENV_FILE = BUILDER_ROOT / ".env"
load_dotenv(ENV_FILE)


# ============================================================
# Config
# ============================================================

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

# Corect pentru Copernicus Data Space Ecosystem / Sentinel Hub
SENTINEL_HUB_TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/"
    "protocol/openid-connect/token"
)

SENTINEL_HUB_PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"

SH_CLIENT_ID = os.getenv("SH_CLIENT_ID", "").strip()
SH_CLIENT_SECRET = os.getenv("SH_CLIENT_SECRET", "").strip()
EE_PROJECT_ID = os.getenv("EE_PROJECT_ID", "").strip()


# ============================================================
# Zone aproximative Iași
# Pentru rezultate mai bune, înlocuim ulterior cercurile cu GeoJSON real.
# ============================================================

IASI_ZONES = [
    {
        "zone_id": "alexandru_01",
        "name": "Alexandru cel Bun",
        "city": "Iasi",
        "latitude": 47.1667,
        "longitude": 27.5500,
        "radius_m": 950,
    },
    {
        "zone_id": "bucium_01",
        "name": "Bucium",
        "city": "Iasi",
        "latitude": 47.1100,
        "longitude": 27.6500,
        "radius_m": 1400,
    },
    {
        "zone_id": "centru_01",
        "name": "Centru",
        "city": "Iasi",
        "latitude": 47.1585,
        "longitude": 27.6014,
        "radius_m": 900,
    },
    {
        "zone_id": "copou_01",
        "name": "Copou",
        "city": "Iasi",
        "latitude": 47.1850,
        "longitude": 27.5660,
        "radius_m": 1300,
    },
    {
        "zone_id": "cug_01",
        "name": "CUG",
        "city": "Iasi",
        "latitude": 47.1200,
        "longitude": 27.5700,
        "radius_m": 1200,
    },
    {
        "zone_id": "dacia_01",
        "name": "Dacia",
        "city": "Iasi",
        "latitude": 47.1660,
        "longitude": 27.5350,
        "radius_m": 850,
    },
    {
        "zone_id": "frumoasa_01",
        "name": "Frumoasa",
        "city": "Iasi",
        "latitude": 47.1300,
        "longitude": 27.5900,
        "radius_m": 900,
    },
    {
        "zone_id": "galata_01",
        "name": "Galata",
        "city": "Iasi",
        "latitude": 47.1450,
        "longitude": 27.5650,
        "radius_m": 1100,
    },
    {
        "zone_id": "nicolina_01",
        "name": "Nicolina",
        "city": "Iasi",
        "latitude": 47.1400,
        "longitude": 27.5850,
        "radius_m": 950,
    },
    {
        "zone_id": "pacurari_01",
        "name": "Pacurari",
        "city": "Iasi",
        "latitude": 47.1750,
        "longitude": 27.5400,
        "radius_m": 1100,
    },
    {
        "zone_id": "podu_ros_01",
        "name": "Podu Ros",
        "city": "Iasi",
        "latitude": 47.1450,
        "longitude": 27.5960,
        "radius_m": 750,
    },
    {
        "zone_id": "tatarasi_01",
        "name": "Tatarasi",
        "city": "Iasi",
        "latitude": 47.1700,
        "longitude": 27.6250,
        "radius_m": 1200,
    },
]


FIELDNAMES = [
    "zone_id",
    "name",
    "city",
    "latitude",
    "longitude",
    "geometry_method",
    "zone_area_m2",

    "osm_green_percent",
    "osm_green_area_m2",
    "osm_source",
    "osm_method",

    "sentinel2_mean_ndvi",
    "sentinel2_median_ndvi",
    "sentinel2_green_pixel_percent",
    "sentinel2_source",
    "sentinel2_date_from",
    "sentinel2_date_to",
    "sentinel2_method",

    "worldcover_vegetation_percent",
    "worldcover_tree_percent",
    "worldcover_grass_percent",
    "worldcover_shrub_percent",
    "worldcover_cropland_percent",
    "worldcover_source",
    "worldcover_year",
    "worldcover_method",

    "copernicus_cgls_tree_cover_percent",
    "copernicus_cgls_grass_cover_percent",
    "copernicus_cgls_shrub_cover_percent",
    "copernicus_cgls_crops_cover_percent",
    "copernicus_cgls_total_vegetation_percent",
    "copernicus_cgls_source",
    "copernicus_cgls_year",
    "copernicus_cgls_method",

    # Scorul final pe care îl va folosi CSV-ul mare de flood risk
    "vegetation_index",

    "confidence",
    "sources_used",
    "notes",
]


# ============================================================
# Utility functions
# ============================================================

def safe_float(value: Any) -> Optional[float]:
    if value is None:
        return None

    try:
        if isinstance(value, str) and value.strip() == "":
            return None

        parsed = float(value)

        if math.isnan(parsed) or math.isinf(parsed):
            return None

        return parsed

    except (TypeError, ValueError):
        return None


def round_or_empty(value: Any, digits: int = 4) -> str:
    parsed = safe_float(value)

    if parsed is None:
        return ""

    return str(round(parsed, digits))


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


def get_local_transformers(lat: float, lon: float) -> tuple[Transformer, Transformer]:
    proj4 = (
        f"+proj=aeqd +lat_0={lat} +lon_0={lon} "
        "+x_0=0 +y_0=0 +datum=WGS84 +units=m +no_defs"
    )

    to_local = Transformer.from_crs("EPSG:4326", proj4, always_xy=True)
    to_wgs84 = Transformer.from_crs(proj4, "EPSG:4326", always_xy=True)

    return to_local, to_wgs84


def make_zone_polygon(zone: dict[str, Any]) -> Polygon:
    lat = float(zone["latitude"])
    lon = float(zone["longitude"])
    radius_m = float(zone["radius_m"])

    to_local, to_wgs84 = get_local_transformers(lat, lon)

    center_wgs84 = Point(lon, lat)
    center_local = transform(to_local.transform, center_wgs84)

    local_circle = center_local.buffer(radius_m, resolution=64)
    wgs84_circle = transform(to_wgs84.transform, local_circle)

    return wgs84_circle


def area_m2(geometry: Any) -> float:
    centroid = geometry.centroid
    to_local, _ = get_local_transformers(centroid.y, centroid.x)
    local_geometry = transform(to_local.transform, geometry)

    return float(local_geometry.area)


# ============================================================
# OSM / Overpass
# ============================================================

def polygon_to_overpass_poly_string(polygon: Polygon) -> str:
    coords = list(polygon.exterior.coords)

    # Overpass cere perechi "lat lon", nu "lon lat".
    pairs = [f"{lat:.7f} {lon:.7f}" for lon, lat in coords]

    return " ".join(pairs)


def build_overpass_query(polygon: Polygon) -> str:
    poly_string = polygon_to_overpass_poly_string(polygon)

    return f"""
[out:json][timeout:120];
(
  way(poly:"{poly_string}")["leisure"~"park|garden|nature_reserve|recreation_ground"];
  way(poly:"{poly_string}")["landuse"~"grass|forest|meadow|orchard|vineyard|recreation_ground|cemetery|allotments"];
  way(poly:"{poly_string}")["natural"~"wood|grassland|scrub|heath"];
);
out geom;
"""


def fetch_osm_green_features_once(polygon: Polygon) -> dict[str, Any]:
    query = build_overpass_query(polygon)

    response = requests.post(
        OVERPASS_URL,
        data={"data": query},
        timeout=180,
        headers={
            "User-Agent": "UrbanRiskTwinVegetationBuilder/1.0"
        },
    )

    response.raise_for_status()
    data = response.json()

    geometries = []

    for element in data.get("elements", []):
        geometry = element.get("geometry", [])

        if not geometry:
            continue

        coords = [(point["lon"], point["lat"]) for point in geometry]

        if len(coords) < 4:
            continue

        if coords[0] != coords[-1]:
            coords.append(coords[0])

        try:
            feature_polygon = Polygon(coords)

            if not feature_polygon.is_valid:
                feature_polygon = feature_polygon.buffer(0)

            if feature_polygon.is_empty:
                continue

            clipped = feature_polygon.intersection(polygon)

            if not clipped.is_empty:
                geometries.append(clipped)

        except Exception:
            continue

    zone_area = area_m2(polygon)

    if not geometries:
        return {
            "green_area_m2": 0.0,
            "green_percent": 0.0,
            "feature_count": 0,
        }

    merged = unary_union(geometries)
    green_area = area_m2(merged)

    green_percent = green_area / zone_area * 100 if zone_area > 0 else 0.0

    return {
        "green_area_m2": green_area,
        "green_percent": clamp(green_percent, 0, 100),
        "feature_count": len(geometries),
    }


def fetch_osm_green_features(polygon: Polygon, retries: int = 3) -> dict[str, Any]:
    last_exception = None

    for attempt in range(1, retries + 1):
        try:
            return fetch_osm_green_features_once(polygon)

        except requests.HTTPError as exception:
            last_exception = exception
            status_code = exception.response.status_code if exception.response else None

            if status_code in [429, 500, 502, 503, 504]:
                wait_seconds = attempt * 8
                print(f"  OSM retry {attempt}/{retries}, astept {wait_seconds}s...")
                time.sleep(wait_seconds)
                continue

            raise

        except Exception as exception:
            last_exception = exception
            wait_seconds = attempt * 5
            print(f"  OSM retry {attempt}/{retries}, astept {wait_seconds}s...")
            time.sleep(wait_seconds)

    raise last_exception


# ============================================================
# Sentinel Hub / Sentinel-2 NDVI
# ============================================================

def get_sentinel_hub_access_token() -> Optional[str]:
    if not SH_CLIENT_ID or not SH_CLIENT_SECRET:
        return None

    response = requests.post(
        SENTINEL_HUB_TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": SH_CLIENT_ID,
            "client_secret": SH_CLIENT_SECRET,
        },
        timeout=60,
    )

    response.raise_for_status()
    token_data = response.json()

    return token_data["access_token"]


def sentinel2_ndvi_evalscript() -> str:
    return """
//VERSION=3
function setup() {
  return {
    input: [{
      bands: ["B04", "B08", "dataMask"]
    }],
    output: {
      bands: 1,
      sampleType: "FLOAT32"
    }
  };
}

function evaluatePixel(sample) {
  if (sample.dataMask === 0) {
    return [-9999];
  }

  let denominator = sample.B08 + sample.B04;

  if (denominator === 0) {
    return [-9999];
  }

  let ndvi = (sample.B08 - sample.B04) / denominator;

  return [ndvi];
}
"""


def fetch_sentinel2_ndvi_stats(
    polygon: Polygon,
    date_from: str,
    date_to: str,
    access_token: str,
) -> dict[str, Any]:
    if rasterio is None or MemoryFile is None:
        raise RuntimeError(
            "rasterio nu este instalat. Instaleaza requirements.txt pentru tool."
        )

    payload = {
        "input": {
            "bounds": {
                "geometry": {
                    "type": "Polygon",
                    "coordinates": [list(map(list, polygon.exterior.coords))],
                },
                "properties": {
                    "crs": "http://www.opengis.net/def/crs/EPSG/0/4326"
                },
            },
            "data": [
                {
                    "type": "sentinel-2-l2a",
                    "dataFilter": {
                        "timeRange": {
                            "from": f"{date_from}T00:00:00Z",
                            "to": f"{date_to}T23:59:59Z",
                        },
                        "mosaickingOrder": "leastCC",
                        "maxCloudCoverage": 30,
                    },
                }
            ],
        },
        "output": {
            "width": 256,
            "height": 256,
            "responses": [
                {
                    "identifier": "default",
                    "format": {
                        "type": "image/tiff"
                    },
                }
            ],
        },
        "evalscript": sentinel2_ndvi_evalscript(),
    }

    response = requests.post(
        SENTINEL_HUB_PROCESS_URL,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "Accept": "image/tiff",
        },
        json=payload,
        timeout=180,
    )

    response.raise_for_status()

    with MemoryFile(response.content) as memory_file:
        with memory_file.open() as dataset:
            ndvi = dataset.read(1).astype("float32")

    valid = ndvi[(ndvi >= -1.0) & (ndvi <= 1.0) & (ndvi != -9999)]

    if valid.size == 0:
        return {
            "mean_ndvi": None,
            "median_ndvi": None,
            "green_pixel_percent": None,
        }

    green_pixels = valid[valid >= 0.30]

    return {
        "mean_ndvi": float(np.mean(valid)),
        "median_ndvi": float(np.median(valid)),
        "green_pixel_percent": float(green_pixels.size / valid.size * 100),
    }


# ============================================================
# Google Earth Engine
# ============================================================

def initialize_earth_engine() -> bool:
    if ee is None:
        print("Google Earth Engine: pachetul earthengine-api nu este instalat")
        return False

    try:
        if EE_PROJECT_ID:
            ee.Initialize(project=EE_PROJECT_ID)
        else:
            ee.Initialize()

        return True

    except Exception as exception:
        print(f"Google Earth Engine: initializare esuata: {exception}")
        return False


def shapely_polygon_to_ee_geometry(polygon: Polygon) -> Any:
    coords = list(map(list, polygon.exterior.coords))

    return ee.Geometry.Polygon(
        coords=[coords],
        proj="EPSG:4326",
        geodesic=False,
    )


def fetch_esa_worldcover_stats(polygon: Polygon) -> dict[str, Any]:
    if ee is None:
        raise RuntimeError("earthengine-api nu este instalat.")

    ee_geometry = shapely_polygon_to_ee_geometry(polygon)

    image = ee.ImageCollection("ESA/WorldCover/v200").first().select("Map")

    histogram_result = image.reduceRegion(
        reducer=ee.Reducer.frequencyHistogram(),
        geometry=ee_geometry,
        scale=10,
        maxPixels=1_000_000_000,
    ).getInfo()

    histogram = histogram_result.get("Map", {})

    if not histogram:
        return {
            "vegetation_percent": None,
            "tree_percent": None,
            "grass_percent": None,
            "shrub_percent": None,
            "cropland_percent": None,
        }

    total_pixels = sum(float(value) for value in histogram.values())

    if total_pixels <= 0:
        return {
            "vegetation_percent": None,
            "tree_percent": None,
            "grass_percent": None,
            "shrub_percent": None,
            "cropland_percent": None,
        }

    def class_percent(class_code: int) -> float:
        value = histogram.get(str(class_code), histogram.get(class_code, 0))
        return float(value) / total_pixels * 100

    # ESA WorldCover classes:
    # 10 Tree cover
    # 20 Shrubland
    # 30 Grassland
    # 40 Cropland
    # 90 Herbaceous wetland
    # 95 Mangroves
    tree_percent = class_percent(10)
    shrub_percent = class_percent(20)
    grass_percent = class_percent(30)
    cropland_percent = class_percent(40)
    wetland_percent = class_percent(90)
    mangrove_percent = class_percent(95)

    vegetation_percent = (
        tree_percent
        + shrub_percent
        + grass_percent
        + cropland_percent
        + wetland_percent
        + mangrove_percent
    )

    return {
        "vegetation_percent": clamp(vegetation_percent, 0, 100),
        "tree_percent": clamp(tree_percent, 0, 100),
        "grass_percent": clamp(grass_percent, 0, 100),
        "shrub_percent": clamp(shrub_percent, 0, 100),
        "cropland_percent": clamp(cropland_percent, 0, 100),
    }


def fetch_copernicus_cgls_stats(polygon: Polygon, year: int = 2019) -> dict[str, Any]:
    if ee is None:
        raise RuntimeError("earthengine-api nu este instalat.")

    ee_geometry = shapely_polygon_to_ee_geometry(polygon)

    image = (
        ee.ImageCollection("COPERNICUS/Landcover/100m/Proba-V-C3/Global")
        .filterDate(f"{year}-01-01", f"{year}-12-31")
        .first()
    )

    if image is None:
        return {
            "tree_cover_percent": None,
            "grass_cover_percent": None,
            "shrub_cover_percent": None,
            "crops_cover_percent": None,
            "total_vegetation_percent": None,
        }

    requested_bands = [
        "tree-coverfraction",
        "grass-coverfraction",
        "shrub-coverfraction",
        "crops-coverfraction",
    ]

    result = image.select(requested_bands).reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=ee_geometry,
        scale=100,
        maxPixels=1_000_000_000,
    ).getInfo()

    tree = safe_float(result.get("tree-coverfraction"))
    grass = safe_float(result.get("grass-coverfraction"))
    shrub = safe_float(result.get("shrub-coverfraction"))
    crops = safe_float(result.get("crops-coverfraction"))

    available = [value for value in [tree, grass, shrub, crops] if value is not None]
    total_veg = sum(available) if available else None

    if total_veg is not None:
        total_veg = clamp(total_veg, 0, 100)

    return {
        "tree_cover_percent": tree,
        "grass_cover_percent": grass,
        "shrub_cover_percent": shrub,
        "crops_cover_percent": crops,
        "total_vegetation_percent": total_veg,
    }


# ============================================================
# Final vegetation index
# ============================================================

def normalize_ndvi_to_index(mean_ndvi: Optional[float]) -> Optional[float]:
    if mean_ndvi is None:
        return None

    # Aproximare:
    # NDVI <= 0.10 => vegetatie foarte slaba
    # NDVI >= 0.70 => vegetatie foarte buna
    return clamp((mean_ndvi - 0.10) / 0.60, 0, 1)


def compute_final_vegetation_index(row: dict[str, Any]) -> tuple[float, str, str]:
    components = []

    worldcover_percent = safe_float(row.get("worldcover_vegetation_percent"))
    sentinel_mean_ndvi = safe_float(row.get("sentinel2_mean_ndvi"))
    osm_percent = safe_float(row.get("osm_green_percent"))
    cgls_total_percent = safe_float(row.get("copernicus_cgls_total_vegetation_percent"))

    if worldcover_percent is not None:
        components.append(("ESA WorldCover", worldcover_percent / 100, 0.35))

    ndvi_index = normalize_ndvi_to_index(sentinel_mean_ndvi)

    if ndvi_index is not None:
        components.append(("Sentinel-2 NDVI", ndvi_index, 0.30))

    if osm_percent is not None:
        components.append(("OpenStreetMap", osm_percent / 100, 0.20))

    if cgls_total_percent is not None:
        components.append(("Copernicus CGLS", cgls_total_percent / 100, 0.15))

    if not components:
        return 0.0, "low", ""

    weighted_sum = sum(value * weight for _, value, weight in components)
    total_weight = sum(weight for _, _, weight in components)

    final_index = weighted_sum / total_weight if total_weight > 0 else 0.0
    source_names = [name for name, _, _ in components]

    if len(components) >= 3:
        confidence = "high"
    elif len(components) == 2:
        confidence = "medium"
    else:
        confidence = "low"

    return clamp(final_index, 0, 1), confidence, "; ".join(source_names)


# ============================================================
# Row processing
# ============================================================

def empty_row_for_zone(zone: dict[str, Any], polygon: Polygon) -> dict[str, Any]:
    return {
        "zone_id": zone["zone_id"],
        "name": zone["name"],
        "city": zone["city"],
        "latitude": zone["latitude"],
        "longitude": zone["longitude"],
        "geometry_method": f"centroid_buffer_radius_{zone['radius_m']}_m",
        "zone_area_m2": round(area_m2(polygon), 2),

        "osm_green_percent": "",
        "osm_green_area_m2": "",
        "osm_source": "",
        "osm_method": "",

        "sentinel2_mean_ndvi": "",
        "sentinel2_median_ndvi": "",
        "sentinel2_green_pixel_percent": "",
        "sentinel2_source": "",
        "sentinel2_date_from": "",
        "sentinel2_date_to": "",
        "sentinel2_method": "",

        "worldcover_vegetation_percent": "",
        "worldcover_tree_percent": "",
        "worldcover_grass_percent": "",
        "worldcover_shrub_percent": "",
        "worldcover_cropland_percent": "",
        "worldcover_source": "",
        "worldcover_year": "",
        "worldcover_method": "",

        "copernicus_cgls_tree_cover_percent": "",
        "copernicus_cgls_grass_cover_percent": "",
        "copernicus_cgls_shrub_cover_percent": "",
        "copernicus_cgls_crops_cover_percent": "",
        "copernicus_cgls_total_vegetation_percent": "",
        "copernicus_cgls_source": "",
        "copernicus_cgls_year": "",
        "copernicus_cgls_method": "",

        "vegetation_index": "",
        "confidence": "",
        "sources_used": "",
        "notes": "",
    }


def process_zone(
    zone: dict[str, Any],
    sentinel_token: Optional[str],
    earth_engine_ready: bool,
    date_from: str,
    date_to: str,
) -> dict[str, Any]:
    polygon = make_zone_polygon(zone)
    row = empty_row_for_zone(zone, polygon)
    notes = []

    print(f"\nProcesez zona: {zone['zone_id']} - {zone['name']}")

    # 1. OpenStreetMap
    try:
        osm_stats = fetch_osm_green_features(polygon)

        row["osm_green_percent"] = round_or_empty(osm_stats["green_percent"], 4)
        row["osm_green_area_m2"] = round_or_empty(osm_stats["green_area_m2"], 2)
        row["osm_source"] = "OpenStreetMap Overpass API"
        row["osm_method"] = "polygon overlay for green OSM tags"

        print(f"  OSM green percent: {row['osm_green_percent']}%")

    except Exception as exception:
        notes.append(f"OSM failed: {exception}")
        print(f"  OSM failed: {exception}")

    # Pauză ca să nu lovim prea agresiv Overpass
    time.sleep(2)

    # 2. Sentinel-2 NDVI
    if sentinel_token:
        try:
            ndvi_stats = fetch_sentinel2_ndvi_stats(
                polygon=polygon,
                date_from=date_from,
                date_to=date_to,
                access_token=sentinel_token,
            )

            row["sentinel2_mean_ndvi"] = round_or_empty(ndvi_stats["mean_ndvi"], 4)
            row["sentinel2_median_ndvi"] = round_or_empty(ndvi_stats["median_ndvi"], 4)
            row["sentinel2_green_pixel_percent"] = round_or_empty(
                ndvi_stats["green_pixel_percent"],
                4,
            )
            row["sentinel2_source"] = "Sentinel-2 L2A via Sentinel Hub Process API"
            row["sentinel2_date_from"] = date_from
            row["sentinel2_date_to"] = date_to
            row["sentinel2_method"] = (
                "NDVI = (B08 - B04) / (B08 + B04), "
                "green pixel threshold NDVI >= 0.30"
            )

            print(f"  Sentinel-2 mean NDVI: {row['sentinel2_mean_ndvi']}")

        except Exception as exception:
            notes.append(f"Sentinel-2 NDVI failed: {exception}")
            print(f"  Sentinel-2 NDVI failed: {exception}")
    else:
        notes.append("Sentinel Hub skipped: SH_CLIENT_ID/SH_CLIENT_SECRET missing")

    # 3. Earth Engine datasets
    if earth_engine_ready:
        try:
            worldcover_stats = fetch_esa_worldcover_stats(polygon)

            row["worldcover_vegetation_percent"] = round_or_empty(
                worldcover_stats["vegetation_percent"],
                4,
            )
            row["worldcover_tree_percent"] = round_or_empty(
                worldcover_stats["tree_percent"],
                4,
            )
            row["worldcover_grass_percent"] = round_or_empty(
                worldcover_stats["grass_percent"],
                4,
            )
            row["worldcover_shrub_percent"] = round_or_empty(
                worldcover_stats["shrub_percent"],
                4,
            )
            row["worldcover_cropland_percent"] = round_or_empty(
                worldcover_stats["cropland_percent"],
                4,
            )
            row["worldcover_source"] = "ESA WorldCover v200"
            row["worldcover_year"] = "2021"
            row["worldcover_method"] = (
                "zonal histogram over ESA WorldCover classes "
                "10, 20, 30, 40, 90, 95"
            )

            print(
                f"  ESA WorldCover vegetation: "
                f"{row['worldcover_vegetation_percent']}%"
            )

        except Exception as exception:
            notes.append(f"ESA WorldCover failed: {exception}")
            print(f"  ESA WorldCover failed: {exception}")

        try:
            cgls_stats = fetch_copernicus_cgls_stats(polygon, year=2019)

            row["copernicus_cgls_tree_cover_percent"] = round_or_empty(
                cgls_stats["tree_cover_percent"],
                4,
            )
            row["copernicus_cgls_grass_cover_percent"] = round_or_empty(
                cgls_stats["grass_cover_percent"],
                4,
            )
            row["copernicus_cgls_shrub_cover_percent"] = round_or_empty(
                cgls_stats["shrub_cover_percent"],
                4,
            )
            row["copernicus_cgls_crops_cover_percent"] = round_or_empty(
                cgls_stats["crops_cover_percent"],
                4,
            )
            row["copernicus_cgls_total_vegetation_percent"] = round_or_empty(
                cgls_stats["total_vegetation_percent"],
                4,
            )
            row["copernicus_cgls_source"] = (
                "Copernicus Global Land Cover CGLS-LC100 via Google Earth Engine"
            )
            row["copernicus_cgls_year"] = "2019"
            row["copernicus_cgls_method"] = (
                "mean cover fractions over zone polygon"
            )

            print(
                f"  Copernicus CGLS vegetation: "
                f"{row['copernicus_cgls_total_vegetation_percent']}%"
            )

        except Exception as exception:
            notes.append(f"Copernicus CGLS failed: {exception}")
            print(f"  Copernicus CGLS failed: {exception}")
    else:
        notes.append("Earth Engine skipped: not initialized")

    vegetation_index, confidence, sources_used = compute_final_vegetation_index(row)

    row["vegetation_index"] = round_or_empty(vegetation_index, 4)
    row["confidence"] = confidence
    row["sources_used"] = sources_used
    row["notes"] = " | ".join(notes)

    print(
        f"  Final vegetation_index: "
        f"{row['vegetation_index']} | confidence={confidence}"
    )

    return row


# ============================================================
# CSV output
# ============================================================

def write_csv(rows: list[dict[str, Any]], output_file: Path) -> None:
    BUILDER_DATA_DIR.mkdir(parents=True, exist_ok=True)

    with output_file.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=FIELDNAMES)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    print("=" * 80)
    print("UrbanRisk Twin - Vegetation Feature Builder")
    print("=" * 80)

    print(f"Builder root: {BUILDER_ROOT}")
    print(f"Output CSV: {OUTPUT_FILE}")

    date_to_obj = datetime.now(timezone.utc).date()
    date_from_obj = date_to_obj - timedelta(days=90)

    date_from = date_from_obj.isoformat()
    date_to = date_to_obj.isoformat()

    print(f"Interval Sentinel-2 NDVI: {date_from} -> {date_to}")

    sentinel_token = None

    if SH_CLIENT_ID and SH_CLIENT_SECRET:
        try:
            sentinel_token = get_sentinel_hub_access_token()
            print("Sentinel Hub: autentificare OK")
        except Exception as exception:
            print(f"Sentinel Hub: autentificare esuata: {exception}")
            sentinel_token = None
    else:
        print("Sentinel Hub: sarit, lipsesc SH_CLIENT_ID / SH_CLIENT_SECRET")

    earth_engine_ready = initialize_earth_engine()

    if earth_engine_ready:
        print("Google Earth Engine: initializare OK")
    else:
        print("Google Earth Engine: sarit")

    rows = []

    for zone in IASI_ZONES:
        row = process_zone(
            zone=zone,
            sentinel_token=sentinel_token,
            earth_engine_ready=earth_engine_ready,
            date_from=date_from,
            date_to=date_to,
        )
        rows.append(row)

    write_csv(rows, OUTPUT_FILE)

    print("\n" + "=" * 80)
    print(f"CSV generat: {OUTPUT_FILE}")
    print(f"Numar zone: {len(rows)}")
    print("=" * 80)


if __name__ == "__main__":
    main()