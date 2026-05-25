from app.risk_engine.utils import to_float, clamp, normalize


def calculate_heat_risk(
    zone: dict,
    temperature: float | None = None,
    humidity: float | None = None
) -> int:
    zone_temperature = to_float(
        temperature if temperature is not None else zone.get("temperature"),
        default=25.0
    )

    zone_humidity = to_float(
        humidity if humidity is not None else zone.get("humidity"),
        default=45.0
    )

    vegetation_index = to_float(zone.get("vegetation_index"), default=0.5)
    urban_density = to_float(zone.get("urban_density"), default=0.5)

    temperature_score = normalize(zone_temperature, 25.0, 40.0)

    humidity_score = normalize(zone_humidity, 35.0, 80.0)

    weather_hazard_score = (
        0.85 * temperature_score +
        0.15 * humidity_score
    )

    low_vegetation_score = 1.0 - clamp(vegetation_index)
    urban_density_score = clamp(urban_density)

    urban_vulnerability_score = (
        0.55 * low_vegetation_score +
        0.45 * urban_density_score
    )

    heat_risk = weather_hazard_score * (
        0.75 + 0.25 * urban_vulnerability_score
    )

    return round(clamp(heat_risk) * 100)