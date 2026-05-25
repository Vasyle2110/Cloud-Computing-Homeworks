from flask import Flask, jsonify
from flask_cors import CORS

from app.routes.health_routes import health_bp
from app.routes.zone_routes import zones_bp
from app.routes.risk_routes import risk_bp
from app.routes.recommendation_routes import recommendations_bp
from app.routes.simulation_routes import simulations_bp
from app.routes.processing_routes import processing_bp
from app.routes.ingestion_routes import ingestion_bp

def create_app() -> Flask:
    app = Flask(__name__)

    CORS(
        app,
        resources={
            r"/*": {
                "origins": [
                    "http://localhost:5173",
                    "http://127.0.0.1:5173"
                ]
            }
        }
    )

    app.register_blueprint(health_bp)
    app.register_blueprint(zones_bp)
    app.register_blueprint(risk_bp)
    app.register_blueprint(recommendations_bp)
    app.register_blueprint(simulations_bp)
    app.register_blueprint(processing_bp)
    app.register_blueprint(ingestion_bp)

    @app.errorhandler(404)
    def not_found(error):
        return jsonify({
            "error": "Endpoint not found"
        }), 404

    @app.errorhandler(500)
    def internal_error(error):
        return jsonify({
            "error": "Internal server error"
        }), 500

    return app