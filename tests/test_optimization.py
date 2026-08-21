import numpy as np

from lade_routing.optimization import (
    ALNSSolver,
    CPP_CORE,
    RoutingProblem,
    dynamic_rolling_alns,
    greedy_initial_solution,
    solution_metrics,
    solve_cp_sat,
    validate_solution,
)
from lade_routing.pyvrp_baseline import solve_pyvrp_static_baseline


class Config:
    random_seed = 7
    processing = {
        "dispatch_interval_seconds": 300,
        "synthetic_sla_seconds": 7200,
        "assumed_speed_kph": 20,
        "service_time_seconds": 120,
    }
    optimization = {
        "capacity_factor": 1.5,
        "cp_sat_time_limit_seconds": 2,
        "cp_sat_num_workers": 2,
        "late_penalty_meters_per_second": 1.0,
        "workload_std_penalty_meters": 100.0,
        "alns_iterations": 20,
        "rolling_alns_iterations": 5,
        "alns_removal_fraction": 0.25,
        "alns_reaction_factor": 0.2,
        "alns_cooling_rate": 0.99,
        "alns_segment_size": 5,
    }


def small_problem() -> RoutingProblem:
    points = np.array([[1, 0], [2, 0], [9, 0], [10, 0]], dtype=float)
    starts = np.array([[0, 0], [11, 0]], dtype=float)
    order_distance = np.linalg.norm(points[:, None, :] - points[None, :, :], axis=2)
    start_distance = np.linalg.norm(starts[:, None, :] - points[None, :, :], axis=2)
    return RoutingProblem(
        instance_id="small",
        order_ids=np.arange(4),
        points=points,
        release_seconds=np.zeros(4),
        due_seconds=np.ones(4) * 7200,
        courier_ids=np.array([100, 200]),
        starts=starts,
        capacity=3,
        order_distance=order_distance,
        start_distance=start_distance,
    )


def test_greedy_assigns_every_order_once() -> None:
    problem = small_problem()
    routes = greedy_initial_solution(problem)
    validate_solution(problem, routes)


def test_alns_preserves_feasibility() -> None:
    problem = small_problem()
    result = ALNSSolver(problem, Config()).solve()
    validate_solution(problem, result.routes)


def test_solution_metrics_are_finite() -> None:
    problem = small_problem()
    routes = greedy_initial_solution(problem)
    metrics = solution_metrics(problem, routes, Config())
    assert metrics.distance_m > 0
    assert np.isfinite(metrics.objective_value)
    assert 0 <= metrics.synthetic_sla_late_rate <= 1


def test_cp_sat_decomposition_preserves_feasibility() -> None:
    problem = small_problem()
    routes, metrics, status = solve_cp_sat(problem, Config())
    assert routes is not None
    assert metrics is not None
    assert "assignment_" not in status
    validate_solution(problem, routes)


def test_dynamic_rolling_alns_assigns_every_order_once() -> None:
    problem = small_problem()
    result = dynamic_rolling_alns(problem, Config())
    validate_solution(problem, result["routes"], enforce_capacity=False)
    assert result["replans"] >= 1


def test_pyvrp_static_baseline_preserves_feasibility() -> None:
    problem = small_problem()
    result = solve_pyvrp_static_baseline(
        problem,
        Config(),
        iterations=25,
    )
    validate_solution(problem, result.routes)
    assert result.solver_cost >= 0
    assert result.metrics.distance_m > 0
    assert result.pyvrp_version == "0.14.0"


def test_cpp_core_matches_python_route_operations() -> None:
    if not CPP_CORE.available:
        return
    problem = small_problem()
    route = [0, 2, 3]

    CPP_CORE.enabled = False
    python_distance = solution_metrics(
        problem,
        [route, [1]],
        Config(),
    ).distance_m

    CPP_CORE.enabled = True
    cpp_distance = solution_metrics(
        problem,
        [route, [1]],
        Config(),
    ).distance_m
    assert abs(python_distance - cpp_distance) < 1e-9

    deltas = CPP_CORE.insertion_deltas(
        problem.start_distance,
        problem.order_distance,
        0,
        [0, 3],
        2,
    )
    assert deltas.shape == (3,)
    assert np.all(np.isfinite(deltas))
