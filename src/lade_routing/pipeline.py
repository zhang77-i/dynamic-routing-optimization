from __future__ import annotations

import logging
from pathlib import Path

from .audit import write_report
from .config import load_config
from .db import build_database
from .processing import build_nearest_neighbor_baseline, build_order_events

LOGGER = logging.getLogger(__name__)


def run_pipeline(config_path: str | Path) -> None:
    config = load_config(config_path)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    for key in ("delivery", "roads"):
        if not config.data[key].exists():
            raise FileNotFoundError(f"Missing raw file: {config.data[key]}")

    LOGGER.info("1/4 Building DuckDB delivery and road layers")
    build_database(config)
    LOGGER.info("2/4 Building Jilin road graph, projections and snapped order events")
    events, nodes, edges = build_order_events(config)
    LOGGER.info("3/4 Running nearest-neighbor structural baseline")
    baseline = build_nearest_neighbor_baseline(events, config)
    LOGGER.info("4/4 Writing audit report and metadata")
    write_report(config, events, nodes, edges, baseline)
    LOGGER.info("Pipeline complete: %s", config.root)
