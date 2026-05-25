from flask import Blueprint, jsonify, request

from app.services.simulation_service import simulate_heatwave, simulate_rainfall

simulations_bp = Blueprint("simulations", __name__)


@simulations_bp.post("/simulate/heatwave")
def run_heatwave_simulation():
    payload = request.get_json(silent=True) or {}

    temperature = payload.get("temperature")
    humidity = payload.get("humidity")

    if temperature is None:
        return jsonify({
            "error": "Missing required field: temperature"
        }), 400

    try:
        temperature = float(temperature)
        humidity = float(humidity) if humidity is not None else None
    except (TypeError, ValueError):
        return jsonify({
            "error": "temperature and humidity must be numeric"
        }), 400

    result = simulate_heatwave(
        temperature=temperature,
        humidity=humidity
    )

    return jsonify(result), 200


@simulations_bp.post("/simulate/rainfall")
def rainfall_simulation():
    data = request.get_json() or {}

    rainfall_mm_per_hour = data.get("rainfall_mm_per_hour")
    start_date = data.get("start_date")
    start_hour = data.get("start_hour")
    end_hour = data.get("end_hour")
    end_date = data.get("end_date")

    missing_fields = []

    if rainfall_mm_per_hour is None:
        missing_fields.append("rainfall_mm_per_hour")

    if start_date is None:
        missing_fields.append("start_date")

    if start_hour is None:
        missing_fields.append("start_hour")

    if end_hour is None:
        missing_fields.append("end_hour")

    if missing_fields:
        return jsonify({
            "error": "Missing required fields",
            "missing_fields": missing_fields,
            "expected_body": {
                "rainfall_mm_per_hour": 10,
                "start_date": "2026-05-26",
                "start_hour": 14,
                "end_hour": 18,
                "end_date": "optional, YYYY-MM-DD"
            }
        }), 400

    try:
        result = simulate_rainfall(
            rainfall_mm_per_hour=float(rainfall_mm_per_hour),
            start_date=str(start_date),
            start_hour=int(start_hour),
            end_hour=int(end_hour),
            end_date=str(end_date) if end_date is not None else None
        )

    except ValueError as exc:
        return jsonify({
            "error": "Invalid rainfall simulation input",
            "details": str(exc)
        }), 400

    return jsonify(result), 200