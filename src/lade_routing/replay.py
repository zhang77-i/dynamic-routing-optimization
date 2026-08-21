from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .config import ProjectConfig


@dataclass(frozen=True)
class ReplayBatch:
    decision_time: int
    released_order_ids: tuple[int, ...]


def build_replay_batches(
    release_seconds: pd.Series,
    order_ids: pd.Series,
    interval_seconds: int,
) -> list[ReplayBatch]:
    frame = pd.DataFrame(
        {
            "release_seconds": release_seconds.astype(int),
            "order_id": order_ids.astype(int),
        }
    ).sort_values(["release_seconds", "order_id"])
    frame["decision_time"] = (
        frame["release_seconds"] // interval_seconds * interval_seconds
    )
    return [
        ReplayBatch(
            decision_time=int(decision_time),
            released_order_ids=tuple(group["order_id"].astype(int)),
        )
        for decision_time, group in frame.groupby("decision_time", sort=True)
    ]


def create_benchmark_instances(
    events: pd.DataFrame,
    config: ProjectConfig,
) -> pd.DataFrame:
    output_dir = config.data["instance_manifest"].parent
    output_dir.mkdir(parents=True, exist_ok=True)
    minimum_orders = int(config.processing["minimum_instance_orders"])
    per_region = int(config.processing["instances_per_region"])
    interval = int(config.processing["dispatch_interval_seconds"])

    counts = (
        events.groupby(["region_id", "service_date"], observed=True)
        .size()
        .rename("order_count")
        .reset_index()
    )
    selected = (
        counts.loc[counts["order_count"].ge(minimum_orders)]
        .sort_values(["region_id", "order_count", "service_date"], ascending=[True, False, True])
        .groupby("region_id", observed=True)
        .head(per_region)
        .reset_index(drop=True)
    )

    manifest_rows: list[dict] = []
    for number, row in enumerate(selected.itertuples(index=False), start=1):
        subset = events.loc[
            events["region_id"].eq(row.region_id)
            & events["service_date"].eq(row.service_date)
        ].sort_values(["release_seconds", "order_id"])
        batches = build_replay_batches(
            subset["release_seconds"],
            subset["order_id"],
            interval,
        )
        courier_rows = []
        for courier_id, courier_orders in subset.groupby(
            "courier_id",
            observed=True,
            sort=True,
        ):
            valid_start = courier_orders.loc[
                courier_orders["valid_accept_gps"].fillna(False)
                & courier_orders["accept_x"].notna()
                & courier_orders["accept_y"].notna()
            ].sort_values(["release_seconds", "order_id"])
            if valid_start.empty:
                first = courier_orders.sort_values(
                    ["release_seconds", "order_id"]
                ).iloc[0]
                start_x = float(first["destination_x"])
                start_y = float(first["destination_y"])
                start_source = "first_destination_fallback"
            else:
                first = valid_start.iloc[0]
                start_x = float(first["accept_x"])
                start_y = float(first["accept_y"])
                start_source = "earliest_valid_accept_gps"
            courier_rows.append(
                {
                    "courier_id": int(courier_id),
                    "start_x": start_x,
                    "start_y": start_y,
                    "start_source": start_source,
                }
            )
        instance_id = f"jl_r{int(row.region_id)}_{pd.Timestamp(row.service_date):%m%d}"
        payload = {
            "instance_id": instance_id,
            "service_date_anchor": str(pd.Timestamp(row.service_date).date()),
            "reference_year_is_synthetic": True,
            "region_id": int(row.region_id),
            "dispatch_interval_seconds": interval,
            "couriers": courier_rows,
            "orders": subset[
                [
                    "order_id",
                    "courier_id",
                    "release_seconds",
                    "observed_delivery_seconds",
                    "destination_x",
                    "destination_y",
                    "road_node_id",
                    "snap_distance_m",
                ]
            ].to_dict(orient="records"),
            "release_batches": [
                {
                    "decision_time": batch.decision_time,
                    "released_order_ids": list(batch.released_order_ids),
                }
                for batch in batches
            ],
        }
        target = output_dir / f"{instance_id}.json"
        target.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        manifest_rows.append(
            {
                "instance_id": instance_id,
                "region_id": int(row.region_id),
                "service_date": row.service_date,
                "orders": len(subset),
                "couriers": subset["courier_id"].nunique(),
                "release_batches": len(batches),
                "file": target.name,
            }
        )

    manifest = pd.DataFrame(manifest_rows)
    manifest.to_csv(config.data["instance_manifest"], index=False)
    return manifest
