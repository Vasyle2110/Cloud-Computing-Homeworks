import csv
import math
import os
import time
from pathlib import Path
from typing import Any, Optional

import requests
from dotenv import load_dotenv
from pyproj import Transformer
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import transform, unary_union

try:
    import ee
except ImportError:
    ee = None


# ============================================================
# Paths
# ============================================================

SCRIPT_PATH = Path(__file__).resolve()

# Expected location:
# UrbanRisk_Twin/tools/flood_feature_builder/scripts/build_urban_density.py
BUILDER_ROOT = SCRIPT_PATH.parents[1]
BUILDER_DATA_DIR = BUILDER_ROOT / "data"
OUTPUT_FILE = BUILDER_DATA_DIR / "urban_density_features.csv"

ENV_FILE = BUILDER_ROOT / ".env"
load_dotenv(ENV_FILE)


# ============================================================
# Config
# ============================================================

OVERPASS_URL = "https://overpass-api.de/api/interpreter"
EE_PROJECT_ID = os.getenv("EE_PROJECT_ID", "").strip()


# ============================================================
# Iași zones
# These are approximate circle buffers around representative points.
# Later we can replace them with real GeoJSON polygons.
# ============================================================

IASI_ZONES = [
    {"zone_id": "alexandru_01", "name": "Alexandru cel Bun", "city": "Iasi", "latitude": 47.1667, "longitude": 27.5500, "radius_m": 950},
    {"zone_id": "bucium_01", "name": "Bucium", "city": "Iasi", "latitude": 47.1100, "longitude": 27.6500, "radius_m": 1400},
    {"zone_id": "centru_01", "name": "Centru", "city": "Iasi", "latitude": 47.1585, "longitude": 27.6014, "radius_m": 900},
    {"zone_id": "copou_01", "name": "Copou", "city": "Iasi", "latitude": 47.1850, "longitude": 27.5660, "radius_m": 1300},
    {"zone_id": "cug_01", "name": "CUG", "city": "Iasi", "latitude": 47.1200, "longitude": 27.5700, "radius_m": 1200},
    {"zone_id": "dacia_01", "name": "Dacia", "city": "Iasi", "latitude": 47.1660, "longitude": 27.5350, "radius_m": 850},
    {"zone_id": "frumoasa_01", "name": "Frumoasa", "city": "Iasi", "latitude": 47.1300, "longitude": 27.5900, "radius_m": 900},
    {"zone_id": "galata_01", "name": "Galata", "city": "Iasi", "latitude": 47.1450, "longitude": 27.5650, "radius_m": 1100},
    {"zone_id": "nicolina_01", "name": "Nicolina", "city": "Iasi", "latitude": 47.1400, "longitude": 27.5850, "radius_m": 950},
    {"zone_id": "pacurari_01", "name": "Pacurari", "city": "Iasi", "latitude": 47.1750, "longitude": 27.5400, "radius_m": 1100},
    {"zone_id": "podu_ros_01", "name": "Podu Ros", "city": "Iasi", "latitude": 47.1450, "longitude": 27.5960, "radius_m": 750},
    {"zone_id": "tatarasi_01", "name": "Tatarasi", "city": "Iasi", "latitude": 47.1700, "longitude": 27.6250, "radius_m": 1200},
]


FIELDNAMES = [
    "zone_id", "name", "city", "latitude", "longitude",
    "geometry_method", "zone_area_m2", "zone_area_km2",
    "osm_building_coverage_percent", "osm_building_area_m2",
    "osm_road_length_m", "osm_road_density_km_per_km2",
    "osm_source", "osm_method",
    "worldcover_builtup_percent", "worldcover_source",
    "worldcover_year", "worldcover_method",
    "ghsl_10m_built_surface_percent", "ghsl_10m_built_surface_area_m2",
    "ghsl_10m_source", "ghsl_10m_year", "ghsl_10m_method",
    "ghsl_100m_built_surface_percent", "ghsl_100m_built_surface_area_m2",
    "ghsl_100m_source", "ghsl_100m_year", "ghsl_100m_method",
    "urban_density", "confidence", "sources_used", "notes",
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
    return transform(to_wgs84.transform, local_circle)


def area_m2(geometry: Any) -> float:
    centroid = geometry.centroid
    to_local, _ = get_local_transformers(centroid.y, centroid.x)
    local_geometry = transform(to_local.transform, geometry)
    return float(local_geometry.area)


def length_m(geometry: Any) -> float:
    centroid = geometry.centroid
    to_local, _ = get_local_transformers(centroid.y, centroid.x)
    local_geometry = transform(to_local.transform, geometry)
    return float(local_geometry.length)


# ============================================================
# OpenStreetMap / Overpass
# ============================================================

def polygon_to_overpass_poly_string(polygon: Polygon) -> str:
    coords = list(polygon.exterior.coords)
    # Overpass expects "lat lon", not "lon lat".
    pairs = [f"{lat:.7f} {lon:.7f}" for lon, lat in coords]
    return " ".join(pairs)


def build_overpass_query(polygon: Polygon) -> str:
    poly_string = polygon_to_overpass_poly_string(polygon)
    return f"""
[out:json][timeout:120];
(
  way(poly:"{poly_string}")["building"];
  way(poly:"{poly_string}")["highway"~"motorway|trunk|primary|secondary|tertiary|unclassified|residential|living_street|service"];
);
out geom tags;
"""


def fetch_osm_urban_features_once(polygon: Polygon) -> dict[str, Any]:
    query = build_overpass_query(polygon)
    response = requests.post(
        OVERPASS_URL,
        data={"data": query},
        timeout=180,
        headers={"User-Agent": "UrbanRiskTwinUrbanDensityBuilder/1.0"},
    )
    response.raise_for_status()
    data = response.json()

    building_geometries = []
    road_geometries = []

    for element in data.get("elements", []):
        tags = element.get("tags", {})
        geometry = element.get("geometry", [])
        if not geometry:
            continue

        coords = [(point["lon"], point["lat"]) for point in geometry]

        if "building" in tags:
            if len(coords) < 4:
                continue
            if coords[0] != coords[-1]:
                coords.append(coords[0])
            try:
                building_polygon = Polygon(coords)
                if not building_polygon.is_valid:
                    building_polygon = building_polygon.buffer(0)
                if building_polygon.is_empty:
                    continue
                clipped = building_polygon.intersection(polygon)
                if not clipped.is_empty:
                    building_geometries.append(clipped)
            except Exception:
                continue

        elif "highway" in tags:
            if len(coords) < 2:
                continue
            try:
                road_line = LineString(coords)
                clipped = road_line.intersection(polygon)
                if not clipped.is_empty:
                    road_geometries.append(clipped)
            except Exception:
                continue

    zone_area = area_m2(polygon)
    zone_area_km2 = zone_area / 1_000_000 if zone_area > 0 else 0

    if building_geometries:
        merged_buildings = unary_union(building_geometries)
        building_area = area_m2(merged_buildings)
    else:
        building_area = 0.0

    building_coverage_percent = building_area / zone_area * 100 if zone_area > 0 else 0.0
    road_length = sum(length_m(road_geometry) for road_geometry in road_geometries)
    road_density = (road_length / 1000) / zone_area_km2 if zone_area_km2 > 0 else 0.0

    return {
        "building_area_m2": building_area,
        "building_coverage_percent": clamp(building_coverage_percent, 0, 100),
        "road_length_m": road_length,
        "road_density_km_per_km2": road_density,
        "building_count": len(building_geometries),
        "road_count": len(road_geometries),
    }


def fetch_osm_urban_features(polygon: Polygon, retries: int = 3) -> dict[str, Any]:
    last_exception = None
    for attempt in range(1, retries + 1):
        try:
            return fetch_osm_urban_features_once(polygon)
        except requests.HTTPError as exception:
            last_exception = exception
            status_code = exception.response.status_code if exception.response is not None else None
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
    return ee.Geometry.Polygon([coords], None, False)


def fetch_worldcover_builtup_stats(polygon: Polygon) -> dict[str, Any]:
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
        return {"builtup_percent": None}

    total_pixels = sum(float(value) for value in histogram.values())
    if total_pixels <= 0:
        return {"builtup_percent": None}

    builtup_pixels = histogram.get("50", histogram.get(50, 0))
    builtup_percent = float(builtup_pixels) / total_pixels * 100
    return {"builtup_percent": clamp(builtup_percent, 0, 100)}


def fetch_ghsl_10m_built_surface_stats(polygon: Polygon) -> dict[str, Any]:
    if ee is None:
        raise RuntimeError("earthengine-api nu este instalat.")

    ee_geometry = shapely_polygon_to_ee_geometry(polygon)
    image = ee.Image("JRC/GHSL/P2023A/GHS_BUILT_S_10m/2018").select("built_surface")

    result = image.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=ee_geometry,
        scale=10,
        maxPixels=1_000_000_000,
    ).getInfo()

    built_surface_area_m2 = safe_float(result.get("built_surface"))
    if built_surface_area_m2 is None:
        return {"built_surface_area_m2": None, "built_surface_percent": None}

    zone_area = area_m2(polygon)
    built_surface_percent = built_surface_area_m2 / zone_area * 100 if zone_area > 0 else None

    return {
        "built_surface_area_m2": built_surface_area_m2,
        "built_surface_percent": clamp(built_surface_percent, 0, 100) if built_surface_percent is not None else None,
    }


def fetch_ghsl_100m_built_surface_stats(polygon: Polygon, year: int = 2020) -> dict[str, Any]:
    if ee is None:
        raise RuntimeError("earthengine-api nu este instalat.")

    ee_geometry = shapely_polygon_to_ee_geometry(polygon)
    image = ee.Image(f"JRC/GHSL/P2023A/GHS_BUILT_S/{year}").select("built_surface")

    result = image.reduceRegion(
        reducer=ee.Reducer.sum(),
        geometry=ee_geometry,
        scale=100,
        maxPixels=1_000_000_000,
    ).getInfo()

    built_surface_area_m2 = safe_float(result.get("built_surface"))
    if built_surface_area_m2 is None:
        return {"built_surface_area_m2": None, "built_surface_percent": None}

    zone_area = area_m2(polygon)
    built_surface_percent = built_surface_area_m2 / zone_area * 100 if zone_area > 0 else None

    return {
        "built_surface_area_m2": built_surface_area_m2,
        "built_surface_percent": clamp(built_surface_percent, 0, 100) if built_surface_percent is not None else None,
    }


# ============================================================
# Final urban_density
# ============================================================

def normalize_building_coverage_percent(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    # In dense urban zones, 35-40% building footprint coverage is already high.
    return clamp(value / 40.0, 0, 1)


def normalize_road_density(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    # 12 km road / km2 is high in this simplified model.
    return clamp(value / 12.0, 0, 1)


def compute_final_urban_density(row: dict[str, Any]) -> tuple[float, str, str]:
    components = []

    ghsl_10m_percent = safe_float(row.get("ghsl_10m_built_surface_percent"))
    ghsl_100m_percent = safe_float(row.get("ghsl_100m_built_surface_percent"))
    worldcover_percent = safe_float(row.get("worldcover_builtup_percent"))
    osm_building_percent = safe_float(row.get("osm_building_coverage_percent"))
    osm_road_density = safe_float(row.get("osm_road_density_km_per_km2"))

    # Prefer GHSL 10m. If it fails, use GHSL 100m.
    if ghsl_10m_percent is not None:
        components.append(("GHSL 10m built surface", ghsl_10m_percent / 100, 0.40))
    elif ghsl_100m_percent is not None:
        components.append(("GHSL 100m built surface", ghsl_100m_percent / 100, 0.40))

    if worldcover_percent is not None:
        components.append(("ESA WorldCover built-up", worldcover_percent / 100, 0.25))

    osm_building_index = normalize_building_coverage_percent(osm_building_percent)
    if osm_building_index is not None:
        components.append(("OpenStreetMap buildings", osm_building_index, 0.20))

    road_density_index = normalize_road_density(osm_road_density)
    if road_density_index is not None:
        components.append(("OpenStreetMap roads", road_density_index, 0.15))

    if not components:
        return 0.0, "low", ""

    weighted_sum = sum(value * weight for _, value, weight in components)
    total_weight = sum(weight for _, _, weight in components)
    final_index = weighted_sum / total_weight if total_weight > 0 else 0.0
    source_names = [name for name, _, _ in components]

    if len(components) >= 4:
        confidence = "high"
    elif len(components) >= 2:
        confidence = "medium"
    else:
        confidence = "low"

    return clamp(final_index, 0, 1), confidence, "; ".join(source_names)


# ============================================================
# Row processing
# ============================================================

def empty_row_for_zone(zone: dict[str, Any], polygon: Polygon) -> dict[str, Any]:
    zone_area = area_m2(polygon)

    return {
        "zone_id": zone["zone_id"],
        "name": zone["name"],
        "city": zone["city"],
        "latitude": zone["latitude"],
        "longitude": zone["longitude"],
        "geometry_method": f"centroid_buffer_radius_{zone['radius_m']}_m",
        "zone_area_m2": round(zone_area, 2),
        "zone_area_km2": round(zone_area / 1_000_000, 6),

        "osm_building_coverage_percent": "",
        "osm_building_area_m2": "",
        "osm_road_length_m": "",
        "osm_road_density_km_per_km2": "",
        "osm_source": "",
        "osm_method": "",

        "worldcover_builtup_percent": "",
        "worldcover_source": "",
        "worldcover_year": "",
        "worldcover_method": "",

        "ghsl_10m_built_surface_percent": "",
        "ghsl_10m_built_surface_area_m2": "",
        "ghsl_10m_source": "",
        "ghsl_10m_year": "",
        "ghsl_10m_method": "",

        "ghsl_100m_built_surface_percent": "",
        "ghsl_100m_built_surface_area_m2": "",
        "ghsl_100m_source": "",
        "ghsl_100m_year": "",
        "ghsl_100m_method": "",

        "urban_density": "",
        "confidence": "",
        "sources_used": "",
        "notes": "",
    }


def process_zone(zone: dict[str, Any], earth_engine_ready: bool) -> dict[str, Any]:
    polygon = make_zone_polygon(zone)
    row = empty_row_for_zone(zone, polygon)
    notes = []

    print(f"\nProcesez zona: {zone['zone_id']} - {zone['name']}")

    # 1. OSM buildings + roads
    try:
        osm_stats = fetch_osm_urban_features(polygon)

        row["osm_building_coverage_percent"] = round_or_empty(osm_stats["building_coverage_percent"], 4)
        row["osm_building_area_m2"] = round_or_empty(osm_stats["building_area_m2"], 2)
        row["osm_road_length_m"] = round_or_empty(osm_stats["road_length_m"], 2)
        row["osm_road_density_km_per_km2"] = round_or_empty(osm_stats["road_density_km_per_km2"], 4)
        row["osm_source"] = "OpenStreetMap Overpass API"
        row["osm_method"] = "building footprint coverage and road length density inside zone polygon"

        print(
            f"  OSM buildings: {row['osm_building_coverage_percent']}% | "
            f"roads: {row['osm_road_density_km_per_km2']} km/km2"
        )

    except Exception as exception:
        notes.append(f"OSM failed: {exception}")
        print(f"  OSM failed: {exception}")

    # Pause so Overpass is not hit too aggressively.
    time.sleep(2)

    # 2. Earth Engine sources
    if earth_engine_ready:
        try:
            worldcover_stats = fetch_worldcover_builtup_stats(polygon)

            row["worldcover_builtup_percent"] = round_or_empty(worldcover_stats["builtup_percent"], 4)
            row["worldcover_source"] = "ESA WorldCover v200"
            row["worldcover_year"] = "2021"
            row["worldcover_method"] = "zonal histogram over ESA WorldCover class 50 Built-up"

            print(f"  ESA WorldCover built-up: {row['worldcover_builtup_percent']}%")

        except Exception as exception:
            notes.append(f"ESA WorldCover failed: {exception}")
            print(f"  ESA WorldCover failed: {exception}")

        try:
            ghsl_10m_stats = fetch_ghsl_10m_built_surface_stats(polygon)

            row["ghsl_10m_built_surface_percent"] = round_or_empty(ghsl_10m_stats["built_surface_percent"], 4)
            row["ghsl_10m_built_surface_area_m2"] = round_or_empty(ghsl_10m_stats["built_surface_area_m2"], 2)
            row["ghsl_10m_source"] = "GHSL GHS-BUILT-S 10m via Google Earth Engine"
            row["ghsl_10m_year"] = "2018"
            row["ghsl_10m_method"] = "sum of built_surface m2 over zone divided by zone area"

            print(f"  GHSL 10m built surface: {row['ghsl_10m_built_surface_percent']}%")

        except Exception as exception:
            notes.append(f"GHSL 10m failed: {exception}")
            print(f"  GHSL 10m failed: {exception}")

        try:
            ghsl_100m_stats = fetch_ghsl_100m_built_surface_stats(polygon, year=2020)

            row["ghsl_100m_built_surface_percent"] = round_or_empty(ghsl_100m_stats["built_surface_percent"], 4)
            row["ghsl_100m_built_surface_area_m2"] = round_or_empty(ghsl_100m_stats["built_surface_area_m2"], 2)
            row["ghsl_100m_source"] = "GHSL GHS-BUILT-S 100m via Google Earth Engine"
            row["ghsl_100m_year"] = "2020"
            row["ghsl_100m_method"] = "sum of built_surface m2 over zone divided by zone area"

            print(f"  GHSL 100m built surface: {row['ghsl_100m_built_surface_percent']}%")

        except Exception as exception:
            notes.append(f"GHSL 100m failed: {exception}")
            print(f"  GHSL 100m failed: {exception}")

    else:
        notes.append("Earth Engine skipped: not initialized")

    urban_density, confidence, sources_used = compute_final_urban_density(row)

    row["urban_density"] = round_or_empty(urban_density, 4)
    row["confidence"] = confidence
    row["sources_used"] = sources_used
    row["notes"] = " | ".join(notes)

    print(f"  Final urban_density: {row['urban_density']} | confidence={confidence}")

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
    print("UrbanRisk Twin - Urban Density Feature Builder")
    print("=" * 80)

    print(f"Builder root: {BUILDER_ROOT}")
    print(f"Output CSV: {OUTPUT_FILE}")

    earth_engine_ready = initialize_earth_engine()

    if earth_engine_ready:
        print("Google Earth Engine: initializare OK")
    else:
        print("Google Earth Engine: sarit")

    rows = []

    for zone in IASI_ZONES:
        row = process_zone(zone=zone, earth_engine_ready=earth_engine_ready)
        rows.append(row)

    write_csv(rows, OUTPUT_FILE)

    print("\n" + "=" * 80)
    print(f"CSV generat: {OUTPUT_FILE}")
    print(f"Numar zone: {len(rows)}")
    print("=" * 80)


if __name__ == "__main__":
    main()
