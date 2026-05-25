from datetime import datetime, timezone
from typing import Any

from app.config import USE_FIRESTORE, USE_CLOUD_STORAGE
from app.external_apis.open_meteo_weather_client import OpenMeteoWeatherClient
from app.external_apis.open_meteo_air_quality_client import OpenMeteoAirQualityClient
from app.services.local_storage_service import (
    load_base_zones,
    save_live_zones,
    save_ingestion_status,
    load_ingestion_status
)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _build_live_zone(
    base_zone: dict,
    weather_data: dict,
    air_quality_data: dict,
    updated_at: str
) -> dict:
    live_zone = dict(base_zone)

    rainfall_value = weather_data.get("rainfall_mm")
    if rainfall_value is None:
        rainfall_value = weather_data.get("precipitation")

    live_zone["temperature"] = _safe_float(
        weather_data.get("temperature"),
        default=base_zone.get("temperature", 25)
    )

    live_zone["humidity"] = _safe_float(
        weather_data.get("humidity"),
        default=base_zone.get("humidity", 45)
    )

    live_zone["rainfall_mm"] = _safe_float(
        rainfall_value,
        default=base_zone.get("rainfall_mm", 0)
    )

    live_zone["wind_speed"] = _safe_float(
        weather_data.get("wind_speed"),
        default=0
    )

    live_zone["air_quality_index"] = _safe_float(
        air_quality_data.get("air_quality_index"),
        default=base_zone.get("air_quality_index", 50)
    )

    live_zone["european_aqi"] = _safe_float(
        air_quality_data.get("european_aqi"),
        default=0
    )

    live_zone["pm10"] = _safe_float(
        air_quality_data.get("pm10"),
        default=0
    )

    live_zone["pm2_5"] = _safe_float(
        air_quality_data.get("pm2_5"),
        default=0
    )

    live_zone["carbon_monoxide"] = _safe_float(
        air_quality_data.get("carbon_monoxide"),
        default=0
    )

    live_zone["nitrogen_dioxide"] = _safe_float(
        air_quality_data.get("nitrogen_dioxide"),
        default=0
    )

    live_zone["ozone"] = _safe_float(
        air_quality_data.get("ozone"),
        default=0
    )

    live_zone["data_source"] = {
        "weather": weather_data.get("weather_source", "Open-Meteo Forecast API"),
        "air_quality": air_quality_data.get("air_quality_source", "Open-Meteo Air Quality API"),
        "urban_baseline": "Local urban baseline"
    }

    live_zone["source_times"] = {
        "weather_time": weather_data.get("weather_time"),
        "air_quality_time": air_quality_data.get("air_quality_time")
    }
    live_zone["forecast_timezone"] = "Europe/Bucharest"

    live_zone["weather_hourly"] = weather_data.get("weather_hourly", {})
    live_zone["air_quality_hourly"] = air_quality_data.get("air_quality_hourly", {})

    live_zone["forecast_metadata"] = {
        "weather_timezone": weather_data.get("weather_timezone"),
        "air_quality_timezone": air_quality_data.get("air_quality_timezone"),
        "forecast_days": 2,
        "hourly_resolution": "1h"
    }

    live_zone["last_updated"] = updated_at

    return live_zone


def _persist_to_cloud(live_zones: list[dict], status: dict) -> dict:
    cloud_results = {}

    if USE_FIRESTORE:
        try:
            from app.services.firestore_service import (
                save_zones_to_firestore,
                save_ingestion_status_to_firestore
            )

            firestore_zones_result = save_zones_to_firestore(live_zones)
            firestore_status_result = save_ingestion_status_to_firestore(status)

            cloud_results["firestore"] = {
                "zones": firestore_zones_result,
                "status": firestore_status_result
            }

        except Exception as exc:
            cloud_results["firestore"] = {
                "status": "failed",
                "error": str(exc)
            }

    else:
        cloud_results["firestore"] = {
            "status": "disabled",
            "reason": "USE_FIRESTORE=false"
        }

    if USE_CLOUD_STORAGE:
        try:
            from app.services.cloud_storage_service import upload_live_zones_backup

            storage_result = upload_live_zones_backup(
                zones=live_zones,
                metadata=status
            )

            cloud_results["cloud_storage"] = storage_result

        except Exception as exc:
            cloud_results["cloud_storage"] = {
                "status": "failed",
                "error": str(exc)
            }

    else:
        cloud_results["cloud_storage"] = {
            "status": "disabled",
            "reason": "USE_CLOUD_STORAGE=false"
        }

    return cloud_results


def ingest_live_data() -> dict:
    weather_client = OpenMeteoWeatherClient()
    air_quality_client = OpenMeteoAirQualityClient()

    base_zones = load_base_zones()
    updated_at = datetime.now(timezone.utc).isoformat()

    live_zones = []
    errors = []

    for zone in base_zones:
        zone_id = zone.get("zone_id")
        latitude = zone.get("latitude")
        longitude = zone.get("longitude")

        try:
            weather_data = weather_client.get_current_weather(
                latitude=latitude,
                longitude=longitude
            )

            air_quality_data = air_quality_client.get_current_air_quality(
                latitude=latitude,
                longitude=longitude
            )

            live_zone = _build_live_zone(
                base_zone=zone,
                weather_data=weather_data,
                air_quality_data=air_quality_data,
                updated_at=updated_at
            )

            live_zones.append(live_zone)

        except Exception as exc:
            fallback_zone = dict(zone)
            fallback_zone["last_updated"] = updated_at
            fallback_zone["data_source"] = {
                "weather": "fallback_local_baseline",
                "air_quality": "fallback_local_baseline",
                "urban_baseline": "Local urban baseline"
            }

            live_zones.append(fallback_zone)

            errors.append({
                "zone_id": zone_id,
                "error": str(exc)
            })

    status = {
        "status": "completed_with_errors" if errors else "completed",
        "updated_at": updated_at,
        "zones_total": len(base_zones),
        "zones_updated": len(live_zones),
        "errors_count": len(errors),
        "errors": errors,
        "sources": [
            "Open-Meteo Forecast API",
            "Open-Meteo Air Quality API",
            "Local urban baseline"
        ]
    }

    save_live_zones(live_zones)
    save_ingestion_status(status)

    cloud_persistence = _persist_to_cloud(live_zones, status)

    status["cloud_persistence"] = cloud_persistence

    save_ingestion_status(status)

    return {
        **status,
        "results": live_zones
    }


def get_ingestion_status() -> dict:
    if USE_FIRESTORE:
        try:
            from app.services.firestore_service import load_ingestion_status_from_firestore

            firestore_status = load_ingestion_status_from_firestore()

            if firestore_status:
                return firestore_status

        except Exception as exc:
            print(f"[WARN] Firestore status read failed, falling back to local JSON: {exc}")

    return load_ingestion_status()