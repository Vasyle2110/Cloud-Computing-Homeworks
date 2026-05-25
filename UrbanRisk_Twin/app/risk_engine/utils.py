def to_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(value: float, min_value: float = 0.0, max_value: float = 1.0) -> float:
    return max(min_value, min(value, max_value))


def normalize(value: float, min_value: float, max_value: float) -> float:
    if max_value == min_value:
        return 0.0

    normalized = (value - min_value) / (max_value - min_value)
    return clamp(normalized)