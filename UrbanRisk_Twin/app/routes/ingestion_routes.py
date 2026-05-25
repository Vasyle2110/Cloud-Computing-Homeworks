from flask import Blueprint, jsonify

from app.services.ingestion_service import ingest_live_data, get_ingestion_status
from app.services.zone_service import get_all_zones

ingestion_bp = Blueprint("ingestion", __name__)


@ingestion_bp.post("/ingest/live-data")
def run_live_data_ingestion():
    result = ingest_live_data()
    return jsonify(result), 200


@ingestion_bp.get("/ingest/status")
def read_ingestion_status():
    return jsonify(get_ingestion_status()), 200


@ingestion_bp.get("/data/live-zones")
def read_live_zones():
    zones = get_all_zones(include_risk=False)

    return jsonify({
        "count": len(zones),
        "zones": zones
    }), 200