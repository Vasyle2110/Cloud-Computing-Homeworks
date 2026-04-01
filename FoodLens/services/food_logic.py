from typing import Any


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

    elif "pasta" in labels or "spaghetti" in labels or "noodle" in labels:
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