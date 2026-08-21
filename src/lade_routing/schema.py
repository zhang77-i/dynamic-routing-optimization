from __future__ import annotations

DELIVERY_COLUMNS = {
    "order_id": "BIGINT",
    "region_id": "BIGINT",
    "city": "VARCHAR",
    "courier_id": "BIGINT",
    "lng": "DOUBLE",
    "lat": "DOUBLE",
    "aoi_id": "BIGINT",
    "aoi_type": "BIGINT",
    "accept_time": "VARCHAR",
    "accept_gps_time": "VARCHAR",
    "accept_gps_lng": "DOUBLE",
    "accept_gps_lat": "DOUBLE",
    "delivery_time": "VARCHAR",
    "delivery_gps_time": "VARCHAR",
    "delivery_gps_lng": "DOUBLE",
    "delivery_gps_lat": "DOUBLE",
    "ds": "VARCHAR",
}

ROAD_COLUMNS = {
    "osm_id": "BIGINT",
    "code": "BIGINT",
    "fclass": "VARCHAR",
    "name": "VARCHAR",
    "ref": "VARCHAR",
    "oneway": "VARCHAR",
    "maxspeed": "DOUBLE",
    "layer": "DOUBLE",
    "bridge": "VARCHAR",
    "tunnel": "VARCHAR",
    "city": "VARCHAR",
    "geometry": "VARCHAR",
}


def duckdb_column_map(columns: dict[str, str]) -> str:
    return "{" + ", ".join(
        f"'{column}': '{column_type}'"
        for column, column_type in columns.items()
    ) + "}"
