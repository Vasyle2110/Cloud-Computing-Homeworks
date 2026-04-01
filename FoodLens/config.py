import os

class Config:
    PROJECT_ID = os.getenv("GCP_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", "powerful-decker-477422-h1"))
    BUCKET_NAME = os.getenv("BUCKET_NAME", "foodlens-powerful-decker-477422-h1-usc1")
    FIRESTORE_COLLECTION = os.getenv("FIRESTORE_COLLECTION", "food_analyses")