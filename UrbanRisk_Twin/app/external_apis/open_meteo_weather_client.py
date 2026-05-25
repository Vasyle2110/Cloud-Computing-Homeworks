import requests


OPEN_METEO_FORECAST_URL = "https://api.open-meteo.com/v1/forecast"


def _safe_get(values: list, index: int, default=None):
    try:
        return values[index]
    except (IndexError, TypeError):
        return default


class OpenMeteoWeatherClient:
    def __init__(self, timeout_seconds: int = 15):
        self.timeout_seconds = timeout_seconds

    def get_current_weather(self, latitude: float, longitude: float) -> dict:
        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": ",".join([
                "temperature_2m",
                "relative_humidity_2m",
                "precipitation",
                "rain",
                "wind_speed_10m"
            ]),
            "hourly": ",".join([
                "temperature_2m",
                "relative_humidity_2m",
                "precipitation",
                "rain",
                "wind_speed_10m"
            ]),
            "past_hours": 12,
            "forecast_hours": 48,
            "timezone": "Europe/Bucharest"
        }

        response = requests.get(
            OPEN_METEO_FORECAST_URL,
            params=params,
            timeout=self.timeout_seconds
        )
        response.raise_for_status()

        payload = response.json()
        current = payload.get("current", {})
        hourly = payload.get("hourly", {})

        weather_hourly = self._build_hourly_forecast(hourly)

        return {
            "temperature": current.get("temperature_2m"),
            "humidity": current.get("relative_humidity_2m"),
            "precipitation": current.get("precipitation"),
            "rainfall_mm": current.get("rain"),
            "wind_speed": current.get("wind_speed_10m"),
            "weather_time": current.get("time"),
            "weather_source": "Open-Meteo Forecast API",
            "weather_timezone": payload.get("timezone"),
            "weather_hourly": weather_hourly
        }

    def _build_hourly_forecast(self, hourly: dict) -> dict:
        times = hourly.get("time", [])

        temperatures = hourly.get("temperature_2m", [])
        humidities = hourly.get("relative_humidity_2m", [])
        precipitations = hourly.get("precipitation", [])
        rains = hourly.get("rain", [])
        wind_speeds = hourly.get("wind_speed_10m", [])

        result = {}

        for index, timestamp in enumerate(times):
            rain_value = _safe_get(rains, index)
            precipitation_value = _safe_get(precipitations, index)

            rainfall_mm = rain_value
            if rainfall_mm is None:
                rainfall_mm = precipitation_value

            result[timestamp] = {
                "temperature": _safe_get(temperatures, index),
                "humidity": _safe_get(humidities, index),
                "precipitation": precipitation_value,
                "rainfall_mm": rainfall_mm,
                "wind_speed": _safe_get(wind_speeds, index),
                "weather_time": timestamp
            }

        return result