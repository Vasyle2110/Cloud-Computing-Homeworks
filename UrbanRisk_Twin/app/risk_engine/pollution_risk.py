from app.risk_engine.utils import to_float, clamp, normalize


def calculate_pollution_risk(zone: dict) -> int:
    air_quality_index = to_float(zone.get("air_quality_index"), default=50.0)
    urban_density = to_float(zone.get("urban_density"), default=0.5)
    vegetation_index = to_float(zone.get("vegetation_index"), default=0.5)

    air_quality_score = normalize(air_quality_index, 0.0, 100.0)

    urban_density_score = clamp(urban_density)
    low_vegetation_score = 1.0 - clamp(vegetation_index)

    local_exposure_score = (
        0.65 * urban_density_score +
        0.35 * low_vegetation_score
    )

    pollution_risk = (
        0.85 * air_quality_score +
        0.15 * air_quality_score * local_exposure_score
    )

    return round(clamp(pollution_risk) * 100)