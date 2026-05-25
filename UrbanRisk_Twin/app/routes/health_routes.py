from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__)


@health_bp.get("/")
def index():
    return jsonify({
        "app": "UrbanRisk Twin",
        "status": "running",
        "description": "Cloud-based urban risk analysis platform",
        "version": "1.0.0"
    }), 200


@health_bp.get("/health")
def health_check():
    return jsonify({
        "status": "healthy"
    }), 200