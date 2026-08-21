from __future__ import annotations

import json
import platform
from datetime import datetime

import duckdb
import numpy as np
import pandas as pd
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components

from .config import ProjectConfig
from .db import connect


def _markdown(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "_无记录_"
    display = frame.copy()
    for column in display:
        display[column] = display[column].map(
            lambda value: "" if pd.isna(value) else str(value)
        )
    header = "| " + " | ".join(display.columns) + " |"
    rule = "| " + " | ".join(["---"] * len(display.columns)) + " |"
    rows = [
        "| " + " | ".join(row) + " |"
        for row in display.astype(str).itertuples(index=False, name=None)
    ]
    return "\n".join([header, rule, *rows])


def collect_sql_audit(config: ProjectConfig) -> dict[str, pd.DataFrame]:
    with connect(config, read_only=True) as connection:
        overview = connection.execute(
            """
            SELECT '吉林配送订单' AS dataset, COUNT(*) AS rows,
                   COUNT(DISTINCT courier_id) AS couriers,
                   COUNT(DISTINCT service_date) AS service_days,
                   COUNT(DISTINCT region_id) AS regions
            FROM delivery_clean
            UNION ALL
            SELECT '吉林道路', COUNT(*), NULL, NULL, NULL FROM roads_jilin
            """
        ).fetch_df()
        quality = connection.execute(
            """
            SELECT '重复订单ID' AS check_name, duplicate_order_ids AS issue_count FROM delivery_audit
            UNION ALL SELECT '缺失接单GPS', missing_accept_gps FROM delivery_audit
            UNION ALL SELECT '异常接单GPS', invalid_accept_gps FROM delivery_audit
            UNION ALL SELECT '异常目的地坐标', invalid_destination_gps FROM delivery_audit
            UNION ALL SELECT '非正配送时长', nonpositive_duration FROM delivery_audit
            UNION ALL SELECT '日期字段不一致', date_mismatch FROM delivery_audit
            UNION ALL SELECT '非LINESTRING道路', invalid_linestrings FROM road_audit
            """
        ).fetch_df()
        duration = connection.execute(
            """
            SELECT
                ROUND(MIN(observed_duration_seconds) / 60.0, 2) AS min_minutes,
                ROUND(quantile_cont(observed_duration_seconds, 0.5) / 60.0, 2) AS median_minutes,
                ROUND(quantile_cont(observed_duration_seconds, 0.95) / 60.0, 2) AS p95_minutes,
                ROUND(MAX(observed_duration_seconds) / 60.0, 2) AS max_minutes
            FROM delivery_clean
            WHERE observed_duration_seconds > 0
            """
        ).fetch_df()
    return {"overview": overview, "quality": quality, "duration": duration}


def write_report(
    config: ProjectConfig,
    events: pd.DataFrame,
    nodes: pd.DataFrame,
    edges: pd.DataFrame,
    baseline: pd.DataFrame,
) -> None:
    audit = collect_sql_audit(config)
    tables = config.root / "reports" / "tables"
    tables.mkdir(parents=True, exist_ok=True)
    for name, frame in audit.items():
        frame.to_csv(tables / f"{name}.csv", index=False)

    snap = pd.DataFrame(
        {
            "metric": [
                "订单吸附距离中位数(m)",
                "订单吸附距离P95(m)",
                "订单吸附距离最大值(m)",
                f"超过{config.processing['snap_warning_meters']}m订单",
                "接单GPS有效率",
            ],
            "value": [
                round(float(events["snap_distance_m"].median()), 2),
                round(float(events["snap_distance_m"].quantile(0.95)), 2),
                round(float(events["snap_distance_m"].max()), 2),
                int(
                    events["snap_distance_m"]
                    .gt(float(config.processing["snap_warning_meters"]))
                    .sum()
                ),
                round(float(events["valid_accept_gps"].mean()), 4),
            ],
        }
    )
    snap.to_csv(tables / "snap_quality.csv", index=False)

    adjacency = coo_matrix(
        (
            np.ones(len(edges), dtype=np.int8),
            (
                edges["u"].to_numpy(dtype=np.int64),
                edges["v"].to_numpy(dtype=np.int64),
            ),
        ),
        shape=(len(nodes), len(nodes)),
    ).tocsr()
    component_count, component_labels = connected_components(
        adjacency,
        directed=False,
    )
    component_sizes = np.bincount(component_labels)
    largest_component_share = (
        float(component_sizes.max() / len(nodes))
        if len(nodes)
        else np.nan
    )

    graph = pd.DataFrame(
        {
            "road_nodes": [len(nodes)],
            "directed_edges": [len(edges)],
            "weakly_implied_source_roads": [edges["osm_id"].nunique()],
            "weak_components": [component_count],
            "largest_component_node_share": [round(largest_component_share, 4)],
            "median_edge_length_m": [round(float(edges["length_m"].median()), 2)],
        }
    )
    graph.to_csv(tables / "road_graph.csv", index=False)

    baseline_summary = pd.DataFrame(
        {
            "courier_day_routes": [len(baseline)],
            "median_orders": [round(float(baseline["orders"].median()), 2)],
            "median_historical_km": [
                round(float(baseline["historical_sequence_distance_m"].median() / 1000), 3)
            ],
            "median_nn_km": [
                round(float(baseline["nearest_neighbor_distance_m"].median() / 1000), 3)
            ],
            "median_nn_ratio": [
                round(float(baseline["distance_ratio_nn_vs_historical"].median()), 4)
            ],
        }
    )
    baseline_summary.to_csv(tables / "baseline_summary.csv", index=False)

    manifest = pd.read_csv(config.data["instance_manifest"])
    report = f"""# LaDe 吉林即时配送项目：初步数据与路网报告

生成时间：{datetime.now().astimezone().isoformat(timespec="seconds")}

## 1. 数据概览

{_markdown(audit["overview"])}

## 2. 数据质量

{_markdown(audit["quality"])}

订单 `ds` 和时间字段不含年份。项目使用 `{config.processing["reference_year"]}` 作为**合成锚点年份**，只用于时间排序与动态回放，不将其解释为真实业务年份。

## 3. 历史配送时长

{_markdown(audit["duration"])}

历史配送时长用于审计和回放对照，不直接当作承诺时间窗。后续模型会区分订单释放时间、业务时间窗和历史完成时间。

## 4. 吉林路网

{_markdown(graph)}

道路 `oneway` 取值按 `B=双向、F=正向、T=反向` 构建有向边；缺失限速根据道路等级采用透明的默认速度表。订单 WGS84 经纬度使用 NumPy 转换为 Web Mercator 后再通过 KD 树吸附。

## 5. 坐标吸附质量

{_markdown(snap)}

吸附距离被保留为特征和质量标记，不会为了让数据“看起来干净”而静默删除远距离点。

## 6. 动态回放数据集

- 已生成订单事件流：`data/processed/order_events_jl.parquet`
- 按 `{config.processing["dispatch_interval_seconds"]}` 秒形成订单释放批次
- 已生成 {len(manifest)} 个确定性的“区域—日期”基准实例
- 每个实例保留历史骑手、释放时间、完成时间、投影坐标和路网节点

## 7. 最近邻基线

{_markdown(baseline_summary)}

该对比只使用“起点—目的地序列”的投影直线距离，历史路线由完成时间推断，且最近邻静态基线预先看到了同一骑手当日订单。因此它只用于验证路线数据结构和成本计算，**不能表述为真实配送里程降低**。后续动态基线必须按释放时间逐批决策。

## 8. 下一阶段

1. 动态最近邻和贪心插入：只使用决策时点已释放订单。
2. OR-Tools VRPTW 静态/滚动基线。
3. 完整 ALNS：Random/Worst/Shaw/Route Removal，Greedy/Regret-2/3 Repair。
4. 自适应算子权重、模拟退火接受、2-opt/Relocate/Swap。
5. 路网最短时间缓存、候选节点剪枝和规模压力测试。
6. 业务指标：超时率、总行驶时间、空驶距离、骑手负载离散度和单次重规划耗时。
"""
    report_path = config.root / "reports" / "initial_data_and_network_audit.md"
    report_path.write_text(report, encoding="utf-8")

    metadata = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "python": platform.python_version(),
        "duckdb": duckdb.__version__,
        "pandas": pd.__version__,
        "numpy": np.__version__,
        "orders": int(len(events)),
        "road_nodes": int(len(nodes)),
        "directed_edges": int(len(edges)),
        "benchmark_instances": int(len(manifest)),
        "baseline_routes": int(len(baseline)),
        "random_seed": config.random_seed,
    }
    (config.root / "reports" / "run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
