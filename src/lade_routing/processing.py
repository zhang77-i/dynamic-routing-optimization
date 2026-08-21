from __future__ import annotations

import numpy as np
import pandas as pd

from .config import ProjectConfig
from .db import connect
from .geo import euclidean_route_distance
from .replay import create_benchmark_instances
from .road_graph import build_road_graph, project_and_snap_orders
from .routing import nearest_neighbor_distance


def build_order_events(config: ProjectConfig) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    nodes, edges = build_road_graph(config)
    with connect(config, read_only=True) as connection:
        orders = connection.execute(
            "SELECT * FROM delivery_clean ORDER BY service_date, release_seconds, order_id"
        ).fetch_df()
        courier_summary = connection.execute(
            "SELECT * FROM courier_day_summary ORDER BY service_date, courier_id"
        ).fetch_df()

    events = project_and_snap_orders(orders, nodes)
    event_columns = [
        "order_id",
        "region_id",
        "city",
        "courier_id",
        "service_date",
        "release_timestamp",
        "delivery_timestamp",
        "release_seconds",
        "observed_delivery_seconds",
        "observed_duration_seconds",
        "destination_lng",
        "destination_lat",
        "destination_x",
        "destination_y",
        "road_node_id",
        "snap_distance_m",
        "accept_gps_lng",
        "accept_gps_lat",
        "accept_x",
        "accept_y",
        "accept_road_node_id",
        "accept_snap_distance_m",
        "valid_accept_gps",
        "aoi_id",
        "aoi_type",
    ]
    events = events[event_columns]
    config.data["order_events"].parent.mkdir(parents=True, exist_ok=True)
    events.to_parquet(config.data["order_events"], index=False)
    courier_summary.to_parquet(config.data["courier_day_summary"], index=False)
    create_benchmark_instances(events, config)
    return events, nodes, edges


def _group_start(group: pd.DataFrame) -> np.ndarray:
    valid = group.loc[
        group["valid_accept_gps"].fillna(False)
        & group["accept_x"].notna()
        & group["accept_y"].notna()
    ].sort_values(["release_seconds", "order_id"])
    if not valid.empty:
        return valid.iloc[0][["accept_x", "accept_y"]].to_numpy(dtype=float)
    return group.iloc[0][["destination_x", "destination_y"]].to_numpy(dtype=float)


def build_nearest_neighbor_baseline(
    events: pd.DataFrame,
    config: ProjectConfig,
) -> pd.DataFrame:
    minimum_orders = int(config.processing["minimum_route_orders"])
    rows: list[dict] = []
    grouped = events.groupby(["service_date", "courier_id"], observed=True, sort=True)
    for (service_date, courier_id), group in grouped:
        if len(group) < minimum_orders:
            continue
        start = _group_start(group)
        historical = group.sort_values(["observed_delivery_seconds", "order_id"])
        points = historical[["destination_x", "destination_y"]].to_numpy(dtype=float)
        historical_distance = euclidean_route_distance(points, start)
        order, nearest_distance = nearest_neighbor_distance(points, start)
        rows.append(
            {
                "service_date": service_date,
                "courier_id": int(courier_id),
                "orders": len(group),
                "historical_sequence_distance_m": historical_distance,
                "nearest_neighbor_distance_m": nearest_distance,
                "distance_ratio_nn_vs_historical": (
                    nearest_distance / historical_distance
                    if historical_distance > 0
                    else np.nan
                ),
                "nearest_neighbor_order_ids": ",".join(
                    historical.iloc[order]["order_id"].astype(str)
                ),
            }
        )
    result = pd.DataFrame(rows)
    result.to_parquet(config.data["baseline_results"], index=False)
    return result
