from datetime import datetime, timedelta

from app.services.zone_service import get_all_zones
from app.risk_engine.heat_risk import calculate_heat_risk
from app.risk_engine.flood_risk import calculate_flood_risk
from app.risk_engine.global_risk import classify_risk


def simulate_heatwave(temperature: float, humidity: float | None = None) -> dict:
    zones = get_all_zones(include_risk=True)

    results = []

    for zone in zones:
        simulated_score = calculate_heat_risk(
            zone=zone,
            temperature=temperature,
            humidity=humidity
        )

        results.append({
            "zone_id": zone["zone_id"],
            "name": zone["name"],
            "original_heat_risk": zone["heat_risk"],
            "simulated_heat_risk": simulated_score,
            "simulated_heat_label": classify_risk(simulated_score),
            "difference": simulated_score - zone["heat_risk"]
        })

    return {
        "simulation_type": "heatwave",
        "input": {
            "temperature": temperature,
            "humidity": humidity
        },
        "count": len(results),
        "results": results
    }


def _parse_simulation_start(
    start_date: str,
    start_hour: int
) -> datetime:
    if start_hour < 0 or start_hour > 23:
        raise ValueError("start_hour must be between 0 and 23")

    try:
        datetime.strptime(start_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError("start_date must have format YYYY-MM-DD")

    return datetime.strptime(
        f"{start_date}T{start_hour:02d}:00",
        "%Y-%m-%dT%H:%M"
    )


def _build_synthetic_weather_hourly(
    start_time: datetime,
    end_time: datetime,
    rainfall_mm_per_hour: float
) -> dict:
    """
    Builds artificial hourly weather data for the rainfall simulation.

    We include a safety buffer before and after the event because calculate_flood_risk()
    checks rainfall context around the selected hour:
    - previous hours
    - current hour
    - next hours
    """

    weather_hourly = {}

    buffer_start = start_time - timedelta(hours=12)
    buffer_end = end_time + timedelta(hours=12)

    current_time = buffer_start

    while current_time <= buffer_end:
        timestamp = current_time.strftime("%Y-%m-%dT%H:%M")

        if start_time <= current_time <= end_time:
            rainfall = rainfall_mm_per_hour
        else:
            rainfall = 0.0

        weather_hourly[timestamp] = {
            "temperature": None,
            "humidity": None,
            "precipitation": rainfall,
            "rainfall_mm": rainfall,
            "wind_speed": None,
            "weather_time": timestamp
        }

        current_time += timedelta(hours=1)

    return weather_hourly


def _simulate_zone_rainfall_event(
    zone: dict,
    start_time: datetime,
    end_time: datetime,
    rainfall_mm_per_hour: float
) -> dict:
    synthetic_weather_hourly = _build_synthetic_weather_hourly(
        start_time=start_time,
        end_time=end_time,
        rainfall_mm_per_hour=rainfall_mm_per_hour
    )

    timeline = []
    peak_score = 0
    peak_time = None

    current_time = start_time

    while current_time <= end_time:
        timestamp = current_time.strftime("%Y-%m-%dT%H:%M")

        simulated_zone = dict(zone)
        simulated_zone["weather_hourly"] = synthetic_weather_hourly
        simulated_zone["rainfall_mm"] = rainfall_mm_per_hour
        simulated_zone["precipitation"] = rainfall_mm_per_hour
        simulated_zone["requested_forecast"] = {
            "date": current_time.strftime("%Y-%m-%d"),
            "hour": current_time.hour,
            "time": timestamp,
            "timezone": "Europe/Bucharest",
            "mode": "rainfall_simulation"
        }

        score = calculate_flood_risk(simulated_zone)

        timeline.append({
            "time": timestamp,
            "rainfall_mm": rainfall_mm_per_hour,
            "flood_risk": score,
            "flood_label": classify_risk(score)
        })

        if score > peak_score:
            peak_score = score
            peak_time = timestamp

        current_time += timedelta(hours=1)

    return {
        "simulated_flood_risk": peak_score,
        "simulated_flood_label": classify_risk(peak_score),
        "peak_time": peak_time,
        "timeline": timeline
    }


def simulate_rainfall(
    rainfall_mm_per_hour: float,
    start_date: str,
    start_hour: int,
    end_hour: int,
    end_date: str | None = None
) -> dict:
    """
    Simulates a rainfall event.

    Example:
        rainfall_mm_per_hour = 10
        start_date = "2026-05-26"
        start_hour = 14
        end_hour = 18

    Meaning:
        From 14:00 to 18:00, rain falls at 10 mm/hour.

    If end_date is missing, it uses start_date.
    """

    if rainfall_mm_per_hour < 0:
        raise ValueError("rainfall_mm_per_hour must be greater than or equal to 0")

    if end_hour < 0 or end_hour > 23:
        raise ValueError("end_hour must be between 0 and 23")

    if end_date is None:
        end_date = start_date

    start_time = _parse_simulation_start(
        start_date=start_date,
        start_hour=start_hour
    )

    try:
        datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError:
        raise ValueError("end_date must have format YYYY-MM-DD")

    end_time = datetime.strptime(
        f"{end_date}T{end_hour:02d}:00",
        "%Y-%m-%dT%H:%M"
    )

    if end_time < start_time:
        raise ValueError("end_time must be greater than or equal to start_time")

    # For safety. Avoid huge payloads in accidental long simulations.
    duration_hours = int((end_time - start_time).total_seconds() // 3600) + 1

    if duration_hours > 48:
        raise ValueError("rainfall simulation cannot exceed 48 hours")

    zones = get_all_zones(include_risk=True)

    results = []

    for zone in zones:
        simulation = _simulate_zone_rainfall_event(
            zone=zone,
            start_time=start_time,
            end_time=end_time,
            rainfall_mm_per_hour=rainfall_mm_per_hour
        )

        original_flood_risk = zone.get("flood_risk", 0)

        results.append({
            "zone_id": zone["zone_id"],
            "name": zone["name"],
            "original_flood_risk": original_flood_risk,
            "simulated_flood_risk": simulation["simulated_flood_risk"],
            "simulated_flood_label": simulation["simulated_flood_label"],
            "peak_time": simulation["peak_time"],
            "difference": simulation["simulated_flood_risk"] - original_flood_risk,
            "timeline": simulation["timeline"]
        })

    return {
        "simulation_type": "rainfall_event",
        "input": {
            "rainfall_mm_per_hour": rainfall_mm_per_hour,
            "start_date": start_date,
            "start_hour": start_hour,
            "end_date": end_date,
            "end_hour": end_hour,
            "duration_hours": duration_hours
        },
        "count": len(results),
        "results": results
    }