from datetime import datetime, timedelta

from app.risk_engine.utils import to_float, clamp, normalize


RAIN_EPSILON_MM = 0.2


def _parse_forecast_time(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M")
    except ValueError:
        return None


def _format_forecast_time(value: datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M")


def _rainfall_from_hour(hour_data: dict | None) -> float:
    if not isinstance(hour_data, dict):
        return 0.0

    rainfall = hour_data.get("rainfall_mm")

    if rainfall is None:
        rainfall = hour_data.get("rain")

    if rainfall is None:
        rainfall = hour_data.get("precipitation")

    return max(0.0, to_float(rainfall, default=0.0))


def _get_requested_forecast_time(zone: dict) -> str | None:
    requested_forecast = zone.get("requested_forecast") or {}

    if isinstance(requested_forecast, dict):
        forecast_time = requested_forecast.get("time")

        if forecast_time:
            return forecast_time

    source_times = zone.get("source_times") or {}

    if isinstance(source_times, dict):
        weather_time = source_times.get("weather_time")

        if weather_time:
            return weather_time

    return zone.get("weather_time")


def _get_rainfall_at_offset(
    weather_hourly: dict,
    start_time: datetime,
    offset_hours: int
) -> float:
    target_key = _format_forecast_time(start_time + timedelta(hours=offset_hours))

    return _rainfall_from_hour(weather_hourly.get(target_key))


def _sum_rainfall_window(
    weather_hourly: dict,
    start_time: datetime,
    start_offset: int,
    end_offset: int
) -> float:
    total = 0.0

    for offset in range(start_offset, end_offset + 1):
        total += _get_rainfall_at_offset(
            weather_hourly=weather_hourly,
            start_time=start_time,
            offset_hours=offset
        )

    return total


def _max_rainfall_window(
    weather_hourly: dict,
    start_time: datetime,
    start_offset: int,
    end_offset: int
) -> float:
    values = []

    for offset in range(start_offset, end_offset + 1):
        values.append(
            _get_rainfall_at_offset(
                weather_hourly=weather_hourly,
                start_time=start_time,
                offset_hours=offset
            )
        )

    if not values:
        return 0.0

    return max(values)


def _count_wet_hours_window(
    weather_hourly: dict,
    start_time: datetime,
    start_offset: int,
    end_offset: int
) -> int:
    wet_hours = 0

    for offset in range(start_offset, end_offset + 1):
        rainfall = _get_rainfall_at_offset(
            weather_hourly=weather_hourly,
            start_time=start_time,
            offset_hours=offset
        )

        if rainfall >= RAIN_EPSILON_MM:
            wet_hours += 1

    return wet_hours


def _get_rain_event_metrics(zone: dict, fallback_rainfall: float) -> dict:
    weather_hourly = zone.get("weather_hourly") or {}
    forecast_time_key = _get_requested_forecast_time(zone)
    forecast_time = _parse_forecast_time(forecast_time_key)

    if not isinstance(weather_hourly, dict) or forecast_time is None:
        return {
            "rain_current_1h_mm": fallback_rainfall,
            "rain_previous_6h_mm": fallback_rainfall,
            "rain_next_3h_mm": fallback_rainfall,
            "rain_event_total_mm": fallback_rainfall,
            "rain_peak_1h_mm": fallback_rainfall,
            "rain_wet_hours": 1 if fallback_rainfall >= RAIN_EPSILON_MM else 0
        }

    rain_current_1h = _get_rainfall_at_offset(
        weather_hourly=weather_hourly,
        start_time=forecast_time,
        offset_hours=0
    )

    rain_previous_6h = _sum_rainfall_window(
        weather_hourly=weather_hourly,
        start_time=forecast_time,
        start_offset=-5,
        end_offset=0
    )

    rain_next_3h = _sum_rainfall_window(
        weather_hourly=weather_hourly,
        start_time=forecast_time,
        start_offset=0,
        end_offset=2
    )

    rain_event_total = _sum_rainfall_window(
        weather_hourly=weather_hourly,
        start_time=forecast_time,
        start_offset=-6,
        end_offset=3
    )

    rain_peak_1h = _max_rainfall_window(
        weather_hourly=weather_hourly,
        start_time=forecast_time,
        start_offset=-6,
        end_offset=3
    )

    rain_wet_hours = _count_wet_hours_window(
        weather_hourly=weather_hourly,
        start_time=forecast_time,
        start_offset=-6,
        end_offset=3
    )

    return {
        "rain_current_1h_mm": rain_current_1h,
        "rain_previous_6h_mm": rain_previous_6h,
        "rain_next_3h_mm": rain_next_3h,
        "rain_event_total_mm": rain_event_total,
        "rain_peak_1h_mm": rain_peak_1h,
        "rain_wet_hours": rain_wet_hours
    }


def calculate_flood_risk(
    zone: dict,
    rainfall_mm: float | None = None
) -> int:
    zone_rainfall = to_float(
        rainfall_mm if rainfall_mm is not None else zone.get("rainfall_mm"),
        default=0.0
    )

    vegetation_index = to_float(zone.get("vegetation_index"), default=0.5)
    urban_density = to_float(zone.get("urban_density"), default=0.5)

    rain_metrics = _get_rain_event_metrics(
        zone=zone,
        fallback_rainfall=zone_rainfall
    )

    rain_current_1h_mm = rain_metrics["rain_current_1h_mm"]
    rain_previous_6h_mm = rain_metrics["rain_previous_6h_mm"]
    rain_next_3h_mm = rain_metrics["rain_next_3h_mm"]
    rain_event_total_mm = rain_metrics["rain_event_total_mm"]
    rain_peak_1h_mm = rain_metrics["rain_peak_1h_mm"]
    rain_wet_hours = rain_metrics["rain_wet_hours"]

    current_rain_score = normalize(rain_current_1h_mm, 0.0, 20.0)
    peak_rain_score = normalize(rain_peak_1h_mm, 0.0, 20.0)

    previous_6h_score = normalize(rain_previous_6h_mm, 0.0, 35.0)
    next_3h_score = normalize(rain_next_3h_mm, 0.0, 25.0)
    event_total_score = normalize(rain_event_total_mm, 0.0, 45.0)

    duration_score = normalize(float(rain_wet_hours), 0.0, 6.0)

    intensity_event_score = (
        0.45 * current_rain_score +
        0.40 * peak_rain_score +
        0.15 * duration_score
    )

    accumulation_event_score = (
        0.40 * previous_6h_score +
        0.30 * next_3h_score +
        0.20 * event_total_score +
        0.10 * duration_score
    )

    rain_event_score = max(
        intensity_event_score,
        accumulation_event_score
    )

    low_vegetation_score = 1.0 - clamp(vegetation_index)
    urban_density_score = clamp(urban_density)

    urban_vulnerability_score = (
        0.55 * low_vegetation_score +
        0.45 * urban_density_score
    )

    flood_risk = rain_event_score * (
        0.75 + 0.25 * urban_vulnerability_score
    )

    return round(clamp(flood_risk) * 100)