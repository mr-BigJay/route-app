from __future__ import annotations

import json
import math
import urllib.error
import urllib.request
from typing import Any

GILAN_BOUNDS = {
    "lat_min": 36.55,
    "lat_max": 38.55,
    "lng_min": 48.40,
    "lng_max": 50.45,
}

EARTH_RADIUS_KM = 6371.0


def clamp_to_gilan(latitude: float, longitude: float) -> tuple[float, float]:
    latitude = max(GILAN_BOUNDS["lat_min"], min(GILAN_BOUNDS["lat_max"], latitude))
    longitude = max(GILAN_BOUNDS["lng_min"], min(GILAN_BOUNDS["lng_max"], longitude))
    return latitude, longitude


def haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    a = (
        math.sin(delta_lat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lng / 2) ** 2
    )
    return EARTH_RADIUS_KM * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def fetch_osrm_route(
    lat1: float,
    lng1: float,
    lat2: float,
    lng2: float,
    timeout: float = 8.0,
) -> tuple[float, list[list[float]]] | None:
    url = (
        "https://router.project-osrm.org/route/v1/driving/"
        f"{lng1},{lat1};{lng2},{lat2}?overview=full&geometries=geojson"
    )
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, KeyError, IndexError, ValueError):
        return None

    if payload.get("code") != "Ok":
        return None

    route = payload["routes"][0]
    distance_km = float(route["distance"]) / 1000.0
    coordinates = route["geometry"]["coordinates"]
    points = [[float(point[1]), float(point[0])] for point in coordinates]
    return distance_km, points


def estimate_route(
    lat1: float,
    lng1: float,
    lat2: float,
    lng2: float,
) -> dict[str, Any]:
    osrm_result = fetch_osrm_route(lat1, lng1, lat2, lng2)
    if osrm_result is not None:
        distance_km, points = osrm_result
        return {
            "distance_km": distance_km,
            "points": points,
            "mode": "road",
        }

    straight_km = haversine_km(lat1, lng1, lat2, lng2)
    return {
        "distance_km": straight_km * 1.25,
        "points": [[lat1, lng1], [lat2, lng2]],
        "mode": "estimated",
    }
