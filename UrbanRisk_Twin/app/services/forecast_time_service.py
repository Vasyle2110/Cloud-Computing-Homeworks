from copy import deepcopy
from datetime import datetime
from typing import Any


FORECAST_TIMEZONE = "Europe/Bucharest"


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ValueError("hour must be an integer between 0 and 23")


def build_forecast_time_key(date_value: str | None, hour_value: str | int | None) -> str | None:
    """
    Converts query params:
        date=2026-05-26
        hour=14

    into Open-Meteo hourly key:
        2026-05-26T14:00

    If both are missing, returns None, meaning current/latest mode.
    """

    if date_value is None and hour_value is None:
        return None

    if not date_value or hour_value is None:
        raise ValueError("Both date and hour must be provided")

    try:
        datetime.strptime(date_value, "%Y-%m-%d")
    except ValueError:
        raise ValueError("date must have format YYYY-MM-DD")

    hour = _safe_int(hour_value)

    if hour < 0 or hour > 23:
        raise ValueError("hour must be between 0 and 23")

    return f"{date_value}T{hour:02d}:00"


def apply_forecast_time_to_zone(
    zone: dict,
    date_value: str | None = None,
    hour_value: str | int | None = None
) -> dict:
    """
    Returns a copy of the zone.

    If date/hour are missing:
        returns the zone unchanged.

    If date/hour are present:
        reads weather_hourly and air_quality_hourly for that hour,
        then replaces the current weather/air-quality values with forecast values.
    """

    forecast_time_key = build_forecast_time_key(date_value, hour_value)

    if forecast_time_key is None:
        return dict(zone)

    updated_zone = deepcopy(zone)

    weather_hourly = updated_zone.get("weather_hourly") or {}
    air_quality_hourly = updated_zone.get("air_quality_hourly") or {}

    if not isinstance(weather_hourly, dict):
        raise ValueError(
            f"weather_hourly is invalid for zone {updated_zone.get('zone_id')}"
        )

    if not isinstance(air_quality_hourly, dict):
        raise ValueError(
            f"air_quality_hourly is invalid for zone {updated_zone.get('zone_id')}"
        )

    weather_at_time = weather_hourly.get(forecast_time_key)
    air_quality_at_time = air_quality_hourly.get(forecast_time_key)

    if weather_at_time is None:
        raise ValueError(
            f"No weather forecast available for {forecast_time_key} "
            f"in zone {updated_zone.get('zone_id')}"
        )

    if air_quality_at_time is None:
        raise ValueError(
            f"No air quality forecast available for {forecast_time_key} "
            f"in zone {updated_zone.get('zone_id')}"
        )

    updated_zone["temperature"] = weather_at_time.get("temperature")
    updated_zone["humidity"] = weather_at_time.get("humidity")
    updated_zone["precipitation"] = weather_at_time.get("precipitation")
    updated_zone["rainfall_mm"] = weather_at_time.get("rainfall_mm")
    updated_zone["wind_speed"] = weather_at_time.get("wind_speed")

    updated_zone["air_quality_index"] = air_quality_at_time.get("air_quality_index")
    updated_zone["european_aqi"] = air_quality_at_time.get("european_aqi")
    updated_zone["pm10"] = air_quality_at_time.get("pm10")
    updated_zone["pm2_5"] = air_quality_at_time.get("pm2_5")
    updated_zone["carbon_monoxide"] = air_quality_at_time.get("carbon_monoxide")
    updated_zone["nitrogen_dioxide"] = air_quality_at_time.get("nitrogen_dioxide")
    updated_zone["ozone"] = air_quality_at_time.get("ozone")

    source_times = dict(updated_zone.get("source_times") or {})
    source_times["weather_time"] = weather_at_time.get("weather_time", forecast_time_key)
    source_times["air_quality_time"] = air_quality_at_time.get(
        "air_quality_time",
        forecast_time_key
    )
    updated_zone["source_times"] = source_times

    updated_zone["requested_forecast"] = {
        "date": date_value,
        "hour": _safe_int(hour_value),
        "time": forecast_time_key,
        "timezone": updated_zone.get("forecast_timezone", FORECAST_TIMEZONE),
        "mode": "hourly_forecast"
    }

    return updated_zone

def strip_hourly_forecast_payload(zone: dict) -> dict:
    cleaned_zone = dict(zone)

    cleaned_zone.pop("weather_hourly", None)
    cleaned_zone.pop("air_quality_hourly", None)

    return cleaned_zone