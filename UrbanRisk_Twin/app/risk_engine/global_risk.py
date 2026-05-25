from app.risk_engine.heat_risk import calculate_heat_risk
from app.risk_engine.flood_risk import calculate_flood_risk
from app.risk_engine.pollution_risk import calculate_pollution_risk


def classify_risk(score: int) -> str:
    if score <= 33:
        return "Low"

    if score <= 66:
        return "Medium"

    return "High"


def get_dominant_risk_type(
    heat_risk: int,
    flood_risk: int,
    pollution_risk: int
) -> str:
    risks = {
        "heat": heat_risk,
        "flood": flood_risk,
        "pollution": pollution_risk
    }

    return max(risks, key=risks.get)


def calculate_global_risk(
    heat_risk: int,
    flood_risk: int,
    pollution_risk: int
) -> int:
    weighted_average = (
        0.40 * heat_risk +
        0.30 * flood_risk +
        0.30 * pollution_risk
    )

    max_component = max(
        heat_risk,
        flood_risk,
        pollution_risk
    )

    global_score = (
        0.70 * weighted_average +
        0.30 * max_component
    )

    return round(global_score)


def build_risk_profile(zone: dict) -> dict:
    heat_risk = calculate_heat_risk(zone)
    flood_risk = calculate_flood_risk(zone)
    pollution_risk = calculate_pollution_risk(zone)

    global_risk = calculate_global_risk(
        heat_risk=heat_risk,
        flood_risk=flood_risk,
        pollution_risk=pollution_risk
    )

    dominant_risk_type = get_dominant_risk_type(
        heat_risk=heat_risk,
        flood_risk=flood_risk,
        pollution_risk=pollution_risk
    )

    risk_profile = dict(zone)

    risk_profile["heat_risk"] = heat_risk
    risk_profile["flood_risk"] = flood_risk
    risk_profile["pollution_risk"] = pollution_risk
    risk_profile["global_risk"] = global_risk

    risk_profile["heat_label"] = classify_risk(heat_risk)
    risk_profile["flood_label"] = classify_risk(flood_risk)
    risk_profile["pollution_label"] = classify_risk(pollution_risk)
    risk_profile["global_label"] = classify_risk(global_risk)

    risk_profile["dominant_risk_type"] = dominant_risk_type
    risk_profile["dominant_risk_score"] = max(
        heat_risk,
        flood_risk,
        pollution_risk
    )

    return risk_profile