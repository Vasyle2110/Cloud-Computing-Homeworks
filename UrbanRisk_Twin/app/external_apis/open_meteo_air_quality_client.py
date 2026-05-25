import requests


OPEN_METEO_AIR_QUALITY_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"


def _safe_get(values: list, index: int, default=None):
    try:
        return values[index]
    except (IndexError, TypeError):
        return default


class OpenMeteoAirQualityClient:
    def __init__(self, timeout_seconds: int = 15):
        self.timeout_seconds = timeout_seconds

    def get_current_air_quality(self, latitude: float, longitude: float) -> dict:
        variables = [
            "european_aqi",
            "pm10",
            "pm2_5",
            "carbon_monoxide",
            "nitrogen_dioxide",
            "ozone"
        ]

        params = {
            "latitude": latitude,
            "longitude": longitude,
            "current": ",".join(variables),
            "hourly": ",".join(variables),
            "forecast_days": 2,
            "timezone": "Europe/Bucharest"
        }

        response = requests.get(
            OPEN_METEO_AIR_QUALITY_URL,
            params=params,
            timeout=self.timeout_seconds
        )
        response.raise_for_status()

        payload = response.json()
        current = payload.get("current", {})
        hourly = payload.get("hourly", {})

        european_aqi = current.get("european_aqi")
        air_quality_hourly = self._build_hourly_forecast(hourly)

        return {
            "air_quality_index": european_aqi,
            "european_aqi": european_aqi,
            "pm10": current.get("pm10"),
            "pm2_5": current.get("pm2_5"),
            "carbon_monoxide": current.get("carbon_monoxide"),
            "nitrogen_dioxide": current.get("nitrogen_dioxide"),
            "ozone": current.get("ozone"),
            "air_quality_time": current.get("time"),
            "air_quality_source": "Open-Meteo Air Quality API",
            "air_quality_timezone": payload.get("timezone"),
            "air_quality_hourly": air_quality_hourly
        }

    def _build_hourly_forecast(self, hourly: dict) -> dict:
        times = hourly.get("time", [])

        european_aqi_values = hourly.get("european_aqi", [])
        pm10_values = hourly.get("pm10", [])
        pm2_5_values = hourly.get("pm2_5", [])
        carbon_monoxide_values = hourly.get("carbon_monoxide", [])
        nitrogen_dioxide_values = hourly.get("nitrogen_dioxide", [])
        ozone_values = hourly.get("ozone", [])

        result = {}

        for index, timestamp in enumerate(times):
            european_aqi = _safe_get(european_aqi_values, index)

            result[timestamp] = {
                "air_quality_index": european_aqi,
                "european_aqi": european_aqi,
                "pm10": _safe_get(pm10_values, index),
                "pm2_5": _safe_get(pm2_5_values, index),
                "carbon_monoxide": _safe_get(carbon_monoxide_values, index),
                "nitrogen_dioxide": _safe_get(nitrogen_dioxide_values, index),
                "ozone": _safe_get(ozone_values, index),
                "air_quality_time": timestamp
            }

        return result