from flask import Flask, request, jsonify
from google.cloud import vision

from config import Config
from services.storage_service import StorageService, allowed_file
from services.firestore_service import FirestoreService
from services.food_logic import infer_food_data

app = Flask(__name__)

storage_service = StorageService(Config.BUCKET_NAME, Config.PROJECT_ID)
firestore_service = FirestoreService(Config.FIRESTORE_COLLECTION, Config.PROJECT_ID)
vision_client = vision.ImageAnnotatorClient()


@app.get("/")
def home():
    return jsonify({
        "message": "FoodLens backend is running",
        "routes": [
            "GET /",
            "POST /upload",
            "GET /history",
            "GET /result/<doc_id>",
            "POST /analyze/<doc_id>"
        ]
    })


@app.post("/upload")
def upload_image():
    if "image" not in request.files:
        return jsonify({"error": "No image file provided. Use form-data key 'image'."}), 400

    image = request.files["image"]

    if image.filename == "":
        return jsonify({"error": "Empty filename."}), 400

    if not allowed_file(image.filename):
        return jsonify({"error": "Unsupported file type. Allowed: png, jpg, jpeg."}), 400

    upload_result = storage_service.upload_image(image)

    doc_data = {
        "image_name": upload_result["original_name"],
        "blob_name": upload_result["blob_name"],
        "gs_uri": upload_result["gs_uri"],
        "image_url": upload_result["public_url"],
        "status": "uploaded",
        "vision_labels": [],
        "food_category": None,
        "estimated_ingredients": [],
        "possible_allergens": [],
        "meal_profile": None,
        "confidence": 0.0,
    }

    doc_id = firestore_service.create_analysis_document(doc_data)

    return jsonify({
        "message": "Image uploaded successfully.",
        "doc_id": doc_id,
        "status": "uploaded",
        "gs_uri": upload_result["gs_uri"]
    }), 201


@app.get("/history")
def history():
    items = firestore_service.list_analysis_documents(limit=50)
    return jsonify(items), 200


@app.get("/result/<doc_id>")
def result(doc_id: str):
    item = firestore_service.get_analysis_document(doc_id)
    if not item:
        return jsonify({"error": "Document not found."}), 404
    return jsonify(item), 200


@app.post("/analyze/<doc_id>")
def analyze_image(doc_id: str):
    item = firestore_service.get_analysis_document(doc_id)
    if not item:
        return jsonify({"error": "Document not found."}), 404

    gs_uri = item.get("gs_uri")
    if not gs_uri:
        return jsonify({"error": "This document has no gs_uri to analyze."}), 400

    try:
        # Marcam documentul ca fiind in procesare
        firestore_service.update_analysis_document(doc_id, {
            "status": "processing"
        })

        # Folosim Vision API pe imaginea din Cloud Storage
        image = vision.Image(source=vision.ImageSource(image_uri=gs_uri))
        response = vision_client.label_detection(image=image)

        if response.error.message:
            firestore_service.update_analysis_document(doc_id, {
                "status": "failed",
                "error_message": response.error.message
            })
            return jsonify({
                "error": "Vision API returned an error.",
                "details": response.error.message
            }), 500

        vision_labels = [
            {
                "description": label.description,
                "score": float(label.score)
            }
            for label in response.label_annotations
        ]

        inferred = infer_food_data(vision_labels)

        firestore_service.update_analysis_document(doc_id, {
            "status": "processed",
            "vision_labels": vision_labels,
            **inferred
        })

        updated_item = firestore_service.get_analysis_document(doc_id)

        return jsonify({
            "message": "Image analyzed successfully.",
            "doc_id": doc_id,
            "result": updated_item
        }), 200

    except Exception as exc:
        firestore_service.update_analysis_document(doc_id, {
            "status": "failed",
            "error_message": str(exc)
        })
        return jsonify({
            "error": "Analysis failed.",
            "details": str(exc)
        }), 500


if __name__ == "__main__":
    app.run(debug=True)