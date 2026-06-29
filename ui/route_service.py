from __future__ import annotations

import json
from typing import Any

from database.db import DatabaseError, DatabaseManager
from ui.geo_utils import estimate_route


def compute_route_for_pair(
    db: DatabaseManager,
    origin_id: int,
    destination_id: int,
    *,
    force: bool = False,
) -> dict[str, Any]:
    if origin_id == destination_id:
        raise DatabaseError("مبدا و مقصد نمی‌توانند یکسان باشند.")

    if not force:
        cached = db.get_cached_route(origin_id, destination_id)
        if cached:
            points = json.loads(cached["route_points"] or "[]")
            return {
                "origin_id": origin_id,
                "destination_id": destination_id,
                "distance_km": float(cached["distance_km"]),
                "points": points,
                "mode": str(cached.get("route_mode") or "cached"),
                "from_cache": True,
            }

    origin = db.get_location(origin_id)
    destination = db.get_location(destination_id)
    if not origin or not destination:
        raise DatabaseError("نقطه انتخاب‌شده یافت نشد.")
    if origin["latitude"] is None or origin["longitude"] is None:
        raise DatabaseError(f"موقعیت مبدا «{origin['title']}» روی نقشه ثبت نشده است.")
    if destination["latitude"] is None or destination["longitude"] is None:
        raise DatabaseError(f"موقعیت مقصد «{destination['title']}» روی نقشه ثبت نشده است.")

    result = estimate_route(
        float(origin["latitude"]),
        float(origin["longitude"]),
        float(destination["latitude"]),
        float(destination["longitude"]),
    )
    distance_km = float(result["distance_km"])
    points = result["points"]
    mode = str(result["mode"])
    db.save_route_cache(
        origin_id,
        destination_id,
        distance_km,
        json.dumps(points, ensure_ascii=False),
        route_mode=mode,
    )
    return {
        "origin_id": origin_id,
        "destination_id": destination_id,
        "distance_km": distance_km,
        "points": points,
        "mode": mode,
        "from_cache": False,
    }


def compute_route_from_pair_row(
    db: DatabaseManager,
    pair: dict[str, Any],
    *,
    force: bool = False,
) -> dict[str, Any]:
    return compute_route_for_pair(
        db,
        int(pair["origin_id"]),
        int(pair["destination_id"]),
        force=force,
    )
