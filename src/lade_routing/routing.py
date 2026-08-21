from __future__ import annotations

import numpy as np

from .geo import euclidean_route_distance


def nearest_neighbor_indices(points_xy: np.ndarray, start_xy: np.ndarray) -> np.ndarray:
    points = np.asarray(points_xy, dtype=np.float64)
    if len(points) == 0:
        return np.array([], dtype=np.int64)

    unvisited = np.ones(len(points), dtype=bool)
    order = np.empty(len(points), dtype=np.int64)
    current = np.asarray(start_xy, dtype=np.float64)
    for position in range(len(points)):
        candidates = np.flatnonzero(unvisited)
        distances = np.linalg.norm(points[candidates] - current, axis=1)
        chosen = candidates[int(np.argmin(distances))]
        order[position] = chosen
        unvisited[chosen] = False
        current = points[chosen]
    return order


def nearest_neighbor_distance(points_xy: np.ndarray, start_xy: np.ndarray) -> tuple[np.ndarray, float]:
    order = nearest_neighbor_indices(points_xy, start_xy)
    return order, euclidean_route_distance(points_xy[order], start_xy)
