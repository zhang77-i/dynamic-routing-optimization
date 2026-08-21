from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from .config import ProjectConfig
from .db import connect
from .geo import lonlat_to_web_mercator

DEFAULT_SPEED_KPH = {
    "motorway": 80.0,
    "motorway_link": 50.0,
    "trunk": 60.0,
    "trunk_link": 45.0,
    "primary": 50.0,
    "primary_link": 40.0,
    "secondary": 40.0,
    "secondary_link": 35.0,
    "tertiary": 35.0,
    "tertiary_link": 30.0,
    "residential": 25.0,
    "service": 15.0,
    "living_street": 10.0,
    "unclassified": 25.0,
}


@dataclass(frozen=True)
class ParsedLine:
    points: np.ndarray
    start_x: float
    start_y: float
    end_x: float
    end_y: float
    length_m: float


def parse_linestring(value: str) -> ParsedLine | None:
    if not isinstance(value, str) or not value.startswith("LINESTRING ("):
        return None
    body = value[value.find("(") + 1 : value.rfind(")")]
    coordinates = np.fromstring(body.replace(",", " "), sep=" ", dtype=np.float64)
    if coordinates.size < 4 or coordinates.size % 2:
        return None
    points = coordinates.reshape(-1, 2)
    length = float(np.linalg.norm(np.diff(points, axis=0), axis=1).sum())
    if not np.isfinite(length) or length <= 0:
        return None
    return ParsedLine(
        points=points,
        start_x=float(points[0, 0]),
        start_y=float(points[0, 1]),
        end_x=float(points[-1, 0]),
        end_y=float(points[-1, 1]),
        length_m=length,
    )


def _speed_kph(fclass: str, maxspeed: float) -> float:
    if pd.notna(maxspeed) and float(maxspeed) > 0:
        return float(maxspeed)
    return DEFAULT_SPEED_KPH.get(str(fclass), 25.0)


def build_road_graph(config: ProjectConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    with connect(config, read_only=True) as connection:
        roads = connection.execute(
            """
            SELECT osm_id, fclass, oneway, maxspeed, geometry
            FROM roads_jilin
            ORDER BY osm_id
            """
        ).fetch_df()

    parsed = [parse_linestring(value) for value in roads["geometry"]]
    valid_mask = np.array([line is not None for line in parsed])
    roads = roads.loc[valid_mask].reset_index(drop=True)
    lines = [line for line in parsed if line is not None]

    decimals = int(config.processing["road_node_round_decimals"])
    rounded_lines = [
        np.round(line.points, decimals=decimals)
        for line in lines
    ]
    all_nodes = np.vstack(rounded_lines)
    unique_nodes, inverse = np.unique(all_nodes, axis=0, return_inverse=True)

    nodes = pd.DataFrame(
        {
            "node_id": np.arange(len(unique_nodes), dtype=np.int64),
            "x": unique_nodes[:, 0],
            "y": unique_nodes[:, 1],
        }
    )

    edge_rows: list[dict] = []
    offset = 0
    for index, road in roads.iterrows():
        line = lines[index]
        line_node_ids = inverse[offset : offset + len(line.points)]
        offset += len(line.points)
        speed = _speed_kph(road["fclass"], road["maxspeed"])
        direction = str(road["oneway"]).upper()
        segment_lengths = np.linalg.norm(np.diff(line.points, axis=0), axis=1)
        for segment_index, length_m in enumerate(segment_lengths):
            u = int(line_node_ids[segment_index])
            v = int(line_node_ids[segment_index + 1])
            if u == v or length_m <= 0:
                continue
            base = {
                "osm_id": int(road["osm_id"]),
                "segment_index": segment_index,
                "fclass": road["fclass"],
                "length_m": float(length_m),
                "speed_kph": speed,
                "travel_seconds": float(length_m / (speed / 3.6)),
            }
            if direction in {"B", "", "NAN"}:
                edge_rows.append({**base, "u": u, "v": v})
                edge_rows.append({**base, "u": v, "v": u})
            elif direction == "T":
                edge_rows.append({**base, "u": v, "v": u})
            else:
                edge_rows.append({**base, "u": u, "v": v})

    edges = pd.DataFrame(edge_rows)
    config.data["road_nodes"].parent.mkdir(parents=True, exist_ok=True)
    nodes.to_parquet(config.data["road_nodes"], index=False)
    edges.to_parquet(config.data["road_edges"], index=False)
    return nodes, edges


def project_and_snap_orders(
    orders: pd.DataFrame,
    nodes: pd.DataFrame,
) -> pd.DataFrame:
    frame = orders.copy()
    dest_x, dest_y = lonlat_to_web_mercator(
        frame["destination_lng"].to_numpy(),
        frame["destination_lat"].to_numpy(),
    )
    frame["destination_x"] = dest_x
    frame["destination_y"] = dest_y

    accept_x = np.full(len(frame), np.nan)
    accept_y = np.full(len(frame), np.nan)
    valid_accept = frame["valid_accept_gps"].fillna(False).to_numpy(dtype=bool)
    projected_accept = lonlat_to_web_mercator(
        frame.loc[valid_accept, "accept_gps_lng"].to_numpy(),
        frame.loc[valid_accept, "accept_gps_lat"].to_numpy(),
    )
    accept_x[valid_accept], accept_y[valid_accept] = projected_accept
    frame["accept_x"] = accept_x
    frame["accept_y"] = accept_y

    tree = cKDTree(nodes[["x", "y"]].to_numpy())
    destination_distance, destination_position = tree.query(
        frame[["destination_x", "destination_y"]].to_numpy(),
        k=1,
    )
    frame["road_node_id"] = nodes.iloc[destination_position]["node_id"].to_numpy()
    frame["snap_distance_m"] = destination_distance

    accept_node = np.full(len(frame), -1, dtype=np.int64)
    accept_snap = np.full(len(frame), np.nan)
    if valid_accept.any():
        distance, position = tree.query(
            frame.loc[valid_accept, ["accept_x", "accept_y"]].to_numpy(),
            k=1,
        )
        accept_node[valid_accept] = nodes.iloc[position]["node_id"].to_numpy()
        accept_snap[valid_accept] = distance
    frame["accept_road_node_id"] = accept_node
    frame["accept_snap_distance_m"] = accept_snap
    return frame
