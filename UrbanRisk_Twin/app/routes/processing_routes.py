from flask import Blueprint, jsonify

from app.services.processing_service import process_all_risks

processing_bp = Blueprint("processing", __name__)


@processing_bp.post("/process-risks")
def process_risks():
    result = process_all_risks()
    return jsonify(result), 200