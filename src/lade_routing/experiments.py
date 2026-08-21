from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import numpy as np
import pandas as pd

from .config import ProjectConfig, load_config
from .optimization import (
    ALNSSolver,
    RoutingMetrics,
    dynamic_online_greedy,
    dynamic_rolling_alns,
    greedy_initial_solution,
    load_problem,
    serialize_routes,
    solution_metrics,
    solve_cp_sat,
    validate_solution,
)
from .pyvrp_baseline import solve_pyvrp_static_baseline

LOGGER = logging.getLogger(__name__)


def _record(
    instance_id: str,
    method: str,
    orders: int,
    couriers: int,
    metrics: RoutingMetrics | dict | None,
    runtime_seconds: float,
    *,
    status: str = "ok",
    replans: int | None = None,
) -> dict:
    if metrics is None:
        values = {
            "distance_m": np.nan,
            "objective_value": np.nan,
            "synthetic_sla_late_rate": np.nan,
            "total_lateness_minutes": np.nan,
            "workload_std": np.nan,
        }
    elif isinstance(metrics, dict):
        values = metrics
    else:
        values = {
            "distance_m": metrics.distance_m,
            "objective_value": metrics.objective_value,
            "synthetic_sla_late_rate": metrics.synthetic_sla_late_rate,
            "total_lateness_minutes": metrics.total_lateness_minutes,
            "workload_std": metrics.workload_std,
        }
    distance_m = float(values["distance_m"])
    return {
        "instance_id": instance_id,
        "method": method,
        "orders": orders,
        "couriers": couriers,
        "distance_m": distance_m,
        "distance_km": distance_m / 1000.0,
        "objective_value": float(values["objective_value"]),
        "runtime_seconds": runtime_seconds,
        "synthetic_sla_late_rate": float(
            values["synthetic_sla_late_rate"]
        ),
        "total_lateness_minutes": float(
            values["total_lateness_minutes"]
        ),
        "workload_std": float(values["workload_std"]),
        "replans": replans,
        "status": status,
    }


def _write_solution(
    directory: Path,
    problem,
    method: str,
    routes,
    extra: dict | None = None,
) -> None:
    payload = {
        "instance_id": problem.instance_id,
        "method": method,
        "objective": (
            "projected open-route distance + synthetic SLA lateness "
            "+ workload imbalance"
        ),
        "routes": serialize_routes(problem, routes),
    }
    if extra:
        payload.update(extra)
    (directory / f"{problem.instance_id}__{method}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _markdown(frame: pd.DataFrame) -> str:
    display = frame.copy()
    for column in display.select_dtypes(include=[np.number]):
        display[column] = display[column].map(
            lambda value: "" if pd.isna(value) else f"{value:.4f}"
        )
    header = "| " + " | ".join(display.columns) + " |"
    rule = "| " + " | ".join(["---"] * len(display.columns)) + " |"
    rows = [
        "| " + " | ".join(map(str, row)) + " |"
        for row in display.itertuples(index=False, name=None)
    ]
    return "\n".join([header, rule, *rows])


def _relative_improvement(
    frame: pd.DataFrame,
    baseline: str,
    challenger: str,
    metric: str,
) -> float:
    pivot = frame.pivot(
        index="instance_id",
        columns="method",
        values=metric,
    )
    if {baseline, challenger}.issubset(pivot.columns):
        valid = pivot[[baseline, challenger]].dropna()
        valid = valid.loc[valid[baseline].abs().gt(1e-12)]
        if not valid.empty:
            return float(
                (1.0 - valid[challenger] / valid[baseline]).mean()
            )
    return float("nan")


def _run_instance(problem, config: ProjectConfig, solution_dir: Path) -> list[dict]:
    rows: list[dict] = []

    started = time.perf_counter()
    dynamic_greedy = dynamic_online_greedy(problem, config)
    runtime = time.perf_counter() - started
    rows.append(
        _record(
            problem.instance_id,
            "dynamic_online_greedy",
            problem.order_count,
            problem.vehicle_count,
            dynamic_greedy,
            runtime,
        )
    )
    _write_solution(
        solution_dir,
        problem,
        "dynamic_online_greedy",
        dynamic_greedy["routes"],
        {
            "information_set": "orders released up to the current dispatch batch",
            "synthetic_sla_seconds": config.processing[
                "synthetic_sla_seconds"
            ],
        },
    )

    started = time.perf_counter()
    rolling = dynamic_rolling_alns(problem, config)
    runtime = time.perf_counter() - started
    rows.append(
        _record(
            problem.instance_id,
            "dynamic_rolling_alns",
            problem.order_count,
            problem.vehicle_count,
            rolling,
            runtime,
            replans=int(rolling["replans"]),
        )
    )
    _write_solution(
        solution_dir,
        problem,
        "dynamic_rolling_alns",
        rolling["routes"],
        {
            "information_set": "orders released up to the current dispatch batch",
            "replans": rolling["replans"],
            "optimization_seconds": rolling["optimization_seconds"],
            "commitment": "one next stop per idle courier is frozen after each replan",
        },
    )

    started = time.perf_counter()
    greedy = greedy_initial_solution(problem)
    validate_solution(problem, greedy)
    greedy_metrics = solution_metrics(problem, greedy, config)
    runtime = time.perf_counter() - started
    rows.append(
        _record(
            problem.instance_id,
            "greedy_regret2_offline",
            problem.order_count,
            problem.vehicle_count,
            greedy_metrics,
            runtime,
        )
    )
    _write_solution(
        solution_dir,
        problem,
        "greedy_regret2_offline",
        greedy,
        {"information_set": "all orders in the region-day instance"},
    )

    started = time.perf_counter()
    cp_sat_routes, cp_sat_metrics, cp_sat_status = solve_cp_sat(
        problem,
        config,
    )
    runtime = time.perf_counter() - started
    rows.append(
        _record(
            problem.instance_id,
            "ortools_cp_sat_decomposed",
            problem.order_count,
            problem.vehicle_count,
            cp_sat_metrics,
            runtime,
            status=cp_sat_status,
        )
    )
    if cp_sat_routes is not None:
        _write_solution(
            solution_dir,
            problem,
            "ortools_cp_sat_decomposed",
            cp_sat_routes,
            {
                "information_set": "all orders in the region-day instance",
                "decomposition": (
                    "CP-SAT courier assignment followed by CP-SAT open-route "
                    "sequencing for each courier"
                ),
                "time_limit_seconds": config.optimization[
                    "cp_sat_time_limit_seconds"
                ],
                "solver_status": cp_sat_status,
            },
        )

    started = time.perf_counter()
    pyvrp_result = solve_pyvrp_static_baseline(problem, config)
    runtime = time.perf_counter() - started
    rows.append(
        _record(
            problem.instance_id,
            "pyvrp_static_distance",
            problem.order_count,
            problem.vehicle_count,
            pyvrp_result.metrics,
            runtime,
        )
    )
    _write_solution(
        solution_dir,
        problem,
        "pyvrp_static_distance",
        pyvrp_result.routes,
        {
            "information_set": "all orders in the region-day instance",
            "solver": f"PyVRP {pyvrp_result.pyvrp_version}",
            "iterations": pyvrp_result.iterations,
            "solver_cost": pyvrp_result.solver_cost,
            "modelling_note": (
                "Static multi-depot distance baseline; client-to-depot arcs "
                "have zero cost to match the open-route convention"
            ),
        },
    )

    started = time.perf_counter()
    alns = ALNSSolver(problem, config).solve()
    runtime = time.perf_counter() - started
    alns_metrics = {
        "distance_m": alns.distance_m,
        "objective_value": alns.objective_value,
        "synthetic_sla_late_rate": alns.synthetic_sla_late_rate,
        "total_lateness_minutes": alns.total_lateness_minutes,
        "workload_std": float(np.std([len(route) for route in alns.routes])),
    }
    rows.append(
        _record(
            problem.instance_id,
            "alns_offline",
            problem.order_count,
            problem.vehicle_count,
            alns_metrics,
            runtime,
        )
    )
    _write_solution(
        solution_dir,
        problem,
        "alns_offline",
        alns.routes,
        {
            "information_set": "all orders in the region-day instance",
            "iterations": alns.iterations,
            "destroy_weights": alns.destroy_weights,
            "repair_weights": alns.repair_weights,
        },
    )
    return rows


def run_optimization_experiments(config_path: str | Path) -> None:
    config = load_config(config_path)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    manifest = pd.read_csv(config.data["instance_manifest"])
    instance_dir = config.data["instance_manifest"].parent
    solution_dir = (
        config.root / "data" / "processed" / "optimization_solutions"
    )
    solution_dir.mkdir(parents=True, exist_ok=True)
    table_dir = config.root / "reports" / "tables"
    table_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict] = []

    for position, instance in enumerate(
        manifest.itertuples(index=False),
        start=1,
    ):
        problem = load_problem(instance_dir / instance.file, config)
        LOGGER.info(
            "Instance %s/%s: %s (%s orders, %s couriers)",
            position,
            len(manifest),
            problem.instance_id,
            problem.order_count,
            problem.vehicle_count,
        )
        results.extend(_run_instance(problem, config, solution_dir))

    frame = pd.DataFrame(results)
    config.data["optimization_results"].parent.mkdir(
        parents=True,
        exist_ok=True,
    )
    frame.to_csv(
        table_dir / "optimization_instance_results.csv",
        index=False,
    )
    try:
        frame.to_parquet(config.data["optimization_results"], index=False)
    except (ImportError, OSError) as exc:
        LOGGER.warning(
            "Parquet export is unavailable in the current Windows "
            "environment; the complete CSV result has been saved instead: %s",
            exc,
        )
    aggregate = (
        frame.groupby("method", observed=True)
        .agg(
            instances=("instance_id", "nunique"),
            mean_distance_km=("distance_km", "mean"),
            mean_objective=("objective_value", "mean"),
            mean_runtime_seconds=("runtime_seconds", "mean"),
            median_workload_std=("workload_std", "median"),
            mean_synthetic_late_rate=("synthetic_sla_late_rate", "mean"),
            mean_total_lateness_minutes=(
                "total_lateness_minutes",
                "mean",
            ),
            mean_replans=("replans", "mean"),
        )
        .reset_index()
        .sort_values("mean_objective")
    )
    aggregate.to_csv(
        table_dir / "optimization_aggregate.csv",
        index=False,
    )

    alns_objective_improvement = _relative_improvement(
        frame,
        "greedy_regret2_offline",
        "alns_offline",
        "objective_value",
    )
    alns_distance_improvement = _relative_improvement(
        frame,
        "greedy_regret2_offline",
        "alns_offline",
        "distance_m",
    )
    rolling_objective_improvement = _relative_improvement(
        frame,
        "dynamic_online_greedy",
        "dynamic_rolling_alns",
        "objective_value",
    )
    rolling_late_improvement = _relative_improvement(
        frame,
        "dynamic_online_greedy",
        "dynamic_rolling_alns",
        "synthetic_sla_late_rate",
    )

    report = f"""# LaDe 动态配送路径优化：算法实验报告

## 实验范围

- 数据：LaDe 吉林真实末端配送订单；
- 实例：{len(manifest)} 个“区域—日期”实例；
- 规模：每个实例 {int(manifest["orders"].min())}–{int(manifest["orders"].max())} 单、{int(manifest["couriers"].min())}–{int(manifest["couriers"].max())} 名历史活跃骑手；
- 动态调度周期：{config.processing["dispatch_interval_seconds"]} 秒；
- 合成 SLA：{config.processing["synthetic_sla_seconds"] / 3600:.1f} 小时；
- 假设速度：{config.processing["assumed_speed_kph"]} km/h；
- 单点服务时间：{config.processing["service_time_seconds"]} 秒；
- CP-SAT 单实例总时间限制：{config.optimization["cp_sat_time_limit_seconds"]} 秒；
- PyVRP 静态基线：{config.optimization["pyvrp_iterations"]} 次迭代；
- 离线 ALNS：{config.optimization["alns_iterations"]} 次迭代；
- 动态滚动 ALNS：每次重规划 {config.optimization["rolling_alns_iterations"]} 次迭代。

## 方法

1. `dynamic_online_greedy`：只使用当前时点已释放订单，按完成时间、迟到和负载进行在线指派；
2. `dynamic_rolling_alns`：每个调度周期重建未服务订单池，使用 ALNS 规划，并冻结每名空闲骑手的下一站；
3. `greedy_regret2_offline`：全量信息下的 Regret-2 构造基线；
4. `ortools_cp_sat_decomposed`：OR-Tools CP-SAT 完成骑手分配，并对每名骑手的开放路径进行 CP-SAT 排序；
5. `pyvrp_static_distance`：PyVRP 多起点静态距离基线，每名骑手对应一个车辆类型，以零成本返仓弧匹配开放路线口径；
6. `alns_offline`：Random/Worst/Shaw/Route-Segment Destroy，Greedy/Regret-2/Regret-3 Repair，自适应权重、模拟退火和 2-opt。

## 聚合结果

{_markdown(aggregate)}

## 相对改进

- 离线 ALNS 相对 Regret-2 的平均综合目标改进：{alns_objective_improvement:.2%}；
- 离线 ALNS 相对 Regret-2 的平均距离改进：{alns_distance_improvement:.2%}；
- 动态滚动 ALNS 相对在线 Greedy 的平均综合目标改进：{rolling_objective_improvement:.2%}；
- 动态滚动 ALNS 相对在线 Greedy 的平均合成迟到率改进：{rolling_late_improvement:.2%}。

## 口径与边界

- 优化距离采用 Web Mercator 投影直线距离，路线为开放路线，不强制返回起点；
- 路网数据用于道路图构建、连通性审计和订单点吸附；当前算法实验没有把投影直线距离表述成真实道路行驶时间；
- LaDe 不提供平台承诺送达时间，2 小时 SLA 是透明的压力测试假设，不是真实平台超时率；
- 在线方法只能看到当时已释放订单，离线方法可看到实例内全部订单，两类结果用于不同目的，不能只依据距离直接判定公平优劣；
- CP-SAT 使用“分配—单骑手路径”分解，以便在 48–188 单实例上稳定生成可行解；它不是对完整多骑手 VRP 最优性的证明。
- PyVRP 基线优化整数化投影距离，不直接优化本项目的合成 SLA 迟到或负载均衡项，因此只作为外部静态求解器参照。
"""
    (config.root / "reports" / "optimization_report.md").write_text(
        report,
        encoding="utf-8",
    )
    metadata = {
        "instances": len(manifest),
        "methods": aggregate["method"].tolist(),
        "cp_sat_time_limit_seconds": config.optimization[
            "cp_sat_time_limit_seconds"
        ],
        "alns_iterations": config.optimization["alns_iterations"],
        "rolling_alns_iterations": config.optimization[
            "rolling_alns_iterations"
        ],
        "pyvrp_iterations": config.optimization["pyvrp_iterations"],
        "mean_alns_objective_improvement_vs_greedy": (
            alns_objective_improvement
        ),
        "mean_dynamic_rolling_objective_improvement_vs_greedy": (
            rolling_objective_improvement
        ),
    }
    (config.root / "reports" / "optimization_run_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    LOGGER.info("Optimization experiments completed: %s rows", len(frame))
