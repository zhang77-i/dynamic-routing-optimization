from __future__ import annotations

import numpy as np

EARTH_RADIUS_M = 6_378_137.0


def lonlat_to_web_mercator(
    longitude: np.ndarray,
    latitude: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    """Vectorized WGS84 lon/lat to EPSG:3857 coordinates."""
    lon = np.asarray(longitude, dtype=np.float64)
    lat = np.asarray(latitude, dtype=np.float64)
    clipped_lat = np.clip(lat, -85.05112878, 85.05112878)
    x = EARTH_RADIUS_M * np.deg2rad(lon)
    y = EARTH_RADIUS_M * np.log(
        np.tan(np.pi / 4.0 + np.deg2rad(clipped_lat) / 2.0)
    )
    return x, y


def haversine_meters(
    lon1: np.ndarray | float,
    lat1: np.ndarray | float,
    lon2: np.ndarray | float,
    lat2: np.ndarray | float,
) -> np.ndarray:
    lon1_r, lat1_r, lon2_r, lat2_r = np.deg2rad(
        [
            np.asarray(lon1, dtype=np.float64),
            np.asarray(lat1, dtype=np.float64),
            np.asarray(lon2, dtype=np.float64),
            np.asarray(lat2, dtype=np.float64),
        ]
    )
    dlon = lon2_r - lon1_r
    dlat = lat2_r - lat1_r
    hav = np.sin(dlat / 2.0) ** 2 + (
        np.cos(lat1_r) * np.cos(lat2_r) * np.sin(dlon / 2.0) ** 2
    )
    return 2.0 * EARTH_RADIUS_M * np.arcsin(np.sqrt(np.clip(hav, 0.0, 1.0)))


def euclidean_route_distance(points_xy: np.ndarray, start_xy: np.ndarray) -> float:
    if len(points_xy) == 0:
        return 0.0
    path = np.vstack([np.asarray(start_xy, dtype=np.float64), points_xy])
    return float(np.linalg.norm(np.diff(path, axis=0), axis=1).sum())
