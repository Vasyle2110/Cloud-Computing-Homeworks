import os
import time
from typing import Any

import functions_framework
from google.cloud import firestore
from google.cloud import vision

PROJECT_ID = os.getenv("GCP_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT"))
COLLECTION_NAME = os.getenv("FIRESTORE_COLLECTION", "food_analyses")

vision_client = vision.ImageAnnotatorClient()
firestore_client = firestore.Client(project=PROJECT_ID)


def normalize_labels(vision_labels: list[dict[str, Any]]) -> list[str]:
    return [label["description"].lower() for label in vision_labels]


def infer_food_data(vision_labels: list[dict[str, Any]]) -> dict:
    labels = normalize_labels(vision_labels)

    category = "unknown"
    ingredients = []
    allergens = []
    profile = "unclassified"

    if "burger" in labels or "hamburger" in labels or "sandwich" in labels:
        category = "burger"
        ingredients = ["bread", "beef patty", "lettuce", "tomato", "cheese"]
        allergens = ["gluten", "dairy"]
        profile = "processed / high-calorie"

    elif "pizza" in labels:
        category = "pizza"
        ingredients = ["dough", "tomato sauce", "cheese"]
        allergens = ["gluten", "dairy"]
        profile = "carb-heavy"

    elif "salad" in labels:
        category = "salad"
        ingredients = ["lettuce", "tomato", "cucumber", "vegetables"]
        allergens = []
        profile = "fresh / balanced"

    elif "pasta" in labels or "spaghetti" in labels or "fettuccine" in labels or "tagliatelle" in labels or "noodle" in labels:
        category = "pasta"
        ingredients = ["pasta", "sauce", "cheese"]
        allergens = ["gluten", "dairy"]
        profile = "carb-heavy"

    elif "dessert" in labels or "cake" in labels:
        category = "dessert"
        ingredients = ["flour", "sugar", "eggs", "butter"]
        allergens = ["gluten", "eggs", "dairy"]
        profile = "sweet / processed"

    confidence = max((label.get("score", 0.0) for label in vision_labels), default=0.0)

    return {
        "food_category": category,
        "estimated_ingredients": ingredients,
        "possible_allergens": allergens,
        "meal_profile": profile,
        "confidence": round(confidence, 4),
    }


def find_firestore_doc_by_blob_name(blob_name: str):
    query = (
        firestore_client.collection(COLLECTION_NAME)
        .where("blob_name", "==", blob_name)
        .limit(1)
        .stream()
    )

    for doc in query:
        return doc.id, doc.to_dict()

    return None, None


def update_doc(doc_id: str, data: dict):
    firestore_client.collection(COLLECTION_NAME).document(doc_id).update(data)


@functions_framework.cloud_event
def analyze_food_image(cloud_event):
    data = cloud_event.data

    bucket_name = data["bucket"]
    blob_name = data["name"]
    gs_uri = f"gs://{bucket_name}/{blob_name}"

    # retry mic ca sa-i dam timp backendului sa scrie documentul
    doc_id = None
    for _ in range(5):
        found_doc_id, _ = find_firestore_doc_by_blob_name(blob_name)
        if found_doc_id:
            doc_id = found_doc_id
            break
        time.sleep(1)

    if not doc_id:
        print(f"No Firestore document found for blob_name={blob_name}")
        return

    update_doc(doc_id, {"status": "processing"})

    image = vision.Image(source=vision.ImageSource(image_uri=gs_uri))
    response = vision_client.label_detection(image=image)

    if response.error.message:
        update_doc(doc_id, {
            "status": "failed",
            "error_message": response.error.message
        })
        return

    vision_labels = [
        {
            "description": label.description,
            "score": float(label.score)
        }
        for label in response.label_annotations
    ]

    inferred = infer_food_data(vision_labels)

    update_doc(doc_id, {
        "status": "processed",
        "vision_labels": vision_labels,
        **inferred
    })