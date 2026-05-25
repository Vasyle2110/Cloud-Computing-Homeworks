from flask import Blueprint, jsonify, request

from app.services.zone_service import get_all_zones, get_zone_by_id

zones_bp = Blueprint("zones", __name__)


@zones_bp.get("/zones")
def get_zones():
    zones = get_all_zones(include_risk=False)

    return jsonify({
        "count": len(zones),
        "zones": zones
    }), 200


@zones_bp.get("/zones/<zone_id>")
def get_zone(zone_id: str):
    date = request.args.get("date")
    hour = request.args.get("hour")

    try:
        zone = get_zone_by_id(
            zone_id,
            include_risk=True,
            date=date,
            hour=hour
        )
    except ValueError as exc:
        return jsonify({
            "error": "Invalid forecast query",
            "details": str(exc),
            "expected_format": "/zones/<zone_id>?date=YYYY-MM-DD&hour=HH"
        }), 400

    if zone is None:
        return jsonify({
            "error": "Zone not found",
            "zone_id": zone_id
        }), 404

    return jsonify(zone), 200