from flask import Blueprint, jsonify , request

from app.services.zone_service import get_all_zones
from app.risk_engine.heat_risk import calculate_heat_risk
from app.risk_engine.flood_risk import calculate_flood_risk
from app.risk_engine.pollution_risk import calculate_pollution_risk
from app.risk_engine.global_risk import classify_risk

risk_bp = Blueprint("risk", __name__)


def build_short_response(zone: dict, risk_type: str, score: int) -> dict:
    return {
        "zone_id": zone.get("zone_id"),
        "name": zone.get("name"),
        "city": zone.get("city"),
        "latitude": zone.get("latitude"),
        "longitude": zone.get("longitude"),
        "risk_type": risk_type,
        "score": score,
        "label": classify_risk(score)
    }


@risk_bp.get("/risk/heat")
def get_heat_risk():
    zones = get_all_zones(include_risk=False)

    results = [
        build_short_response(zone, "heat", calculate_heat_risk(zone))
        for zone in zones
    ]

    return jsonify({
        "risk_type": "heat",
        "count": len(results),
        "results": results
    }), 200


@risk_bp.get("/risk/flood")
def get_flood_risk():
    zones = get_all_zones(include_risk=False)

    results = [
        build_short_response(zone, "flood", calculate_flood_risk(zone))
        for zone in zones
    ]

    return jsonify({
        "risk_type": "flood",
        "count": len(results),
        "results": results
    }), 200


@risk_bp.get("/risk/pollution")
def get_pollution_risk():
    zones = get_all_zones(include_risk=False)

    results = [
        build_short_response(zone, "pollution", calculate_pollution_risk(zone))
        for zone in zones
    ]

    return jsonify({
        "risk_type": "pollution",
        "count": len(results),
        "results": results
    }), 200


@risk_bp.get("/risk/global")
def get_global_risk():
    date = request.args.get("date")
    hour = request.args.get("hour")

    try:
        results = get_all_zones(
            include_risk=True,
            date=date,
            hour=hour
        )
    except ValueError as exc:
        return jsonify({
            "error": "Invalid forecast query",
            "details": str(exc),
            "expected_format": "/risk/global?date=YYYY-MM-DD&hour=HH"
        }), 400

    high_risk_zones = [
        zone for zone in results
        if zone.get("global_label") == "High"
    ]

    average_global_risk = 0

    if results:
        average_global_risk = round(
            sum(zone.get("global_risk", 0) for zone in results) / len(results),
            2
        )

    response = {
        "risk_type": "global",
        "count": len(results),
        "average_global_risk": average_global_risk,
        "high_risk_count": len(high_risk_zones),
        "results": results
    }

    if date is not None or hour is not None:
        response["forecast_query"] = {
            "date": date,
            "hour": int(hour) if hour is not None and hour.isdigit() else hour,
            "timezone": "Europe/Bucharest"
        }

    return jsonify(response), 200