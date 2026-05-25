from flask import Blueprint, jsonify

from app.services.recommendation_service import build_recommendations_for_zone

recommendations_bp = Blueprint("recommendations", __name__)


@recommendations_bp.get("/recommendations/<zone_id>")
def get_recommendations(zone_id: str):
    response = build_recommendations_for_zone(zone_id)

    if response is None:
        return jsonify({
            "error": "Zone not found",
            "zone_id": zone_id
        }), 404

    return jsonify(response), 200