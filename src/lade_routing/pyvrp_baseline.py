from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import version

import numpy as np

from .config import ProjectConfig
from .optimization import (
    Routes,
    RoutingMetrics,
    RoutingProblem,
    solution_metrics,
    validate_solution,
)


@dataclass(frozen=True)
class PyVRPBaselineResult:
    routes: Routes
    metrics: RoutingMetrics
    solver_cost: int
    iterations: int
    pyvrp_version: str


def _edge_distance(
    problem: RoutingProblem,
    frm: int,
    to: int,
) -> int:
    depots = problem.vehicle_count
    if frm == to or to < depots:
        return 0
    if frm < depots:
        distance = problem.start_distance[frm, to - depots]
    else:
        distance = problem.order_distance[frm - depots, to - depots]
    return max(int(round(float(distance))), 0)


def solve_pyvrp_static_baseline(
    problem: RoutingProblem,
    config: ProjectConfig,
    *,
    iterations: int | None = None,
) -> PyVRPBaselineResult:
    """Solve a static, open-route, multi-depot distance baseline with PyVRP.

    Each courier is represented by one vehicle type with its own start depot.
    Zero-cost client-to-depot arcs remove the artificial return leg, matching
    this repository's open-route distance convention. Distances are rounded to
    integers for PyVRP and all orders are available to this offline baseline.
    """
    try:
        import pyvrp
        from pyvrp.stop import MaxIterations
    except ImportError as exc:  # pragma: no cover - dependency error message
        raise ImportError(
            "PyVRP baseline requires pyvrp; install requirements.txt first."
        ) from exc

    model = pyvrp.Model()
    depots = []
    for vehicle, (x, y) in enumerate(problem.starts):
        location = model.add_location(
            x=float(x),
            y=float(y),
            name=f"courier_start_{int(problem.courier_ids[vehicle])}",
        )
        depots.append(model.add_depot(location=location))

    service_seconds = int(round(config.processing["service_time_seconds"]))
    for order, (x, y) in enumerate(problem.points):
        location = model.add_location(
            x=float(x),
            y=float(y),
            name=f"order_{int(problem.order_ids[order])}",
        )
        model.add_client(
            location=location,
            delivery=1,
            service_duration=max(service_seconds, 0),
        )

    for vehicle, depot in enumerate(depots):
        model.add_vehicle_type(
            num_available=1,
            capacity=problem.capacity,
            start_depot=depot,
            end_depot=depot,
            name=f"courier_{int(problem.courier_ids[vehicle])}",
        )

    locations = model.locations
    speed_mps = float(config.processing["assumed_speed_kph"]) / 3.6
    for frm, frm_location in enumerate(locations):
        for to, to_location in enumerate(locations):
            distance = _edge_distance(problem, frm, to)
            duration = (
                int(np.ceil(distance / speed_mps))
                if distance and speed_mps > 0
                else 0
            )
            model.add_edge(
                frm_location,
                to_location,
                distance=distance,
                duration=duration,
            )

    limit = max(
        int(
            iterations
            if iterations is not None
            else config.optimization["pyvrp_iterations"]
        ),
        1,
    )
    result = model.solve(
        stop=MaxIterations(limit),
        seed=int(config.random_seed),
        display=False,
    )
    if not result.is_feasible():
        raise RuntimeError("PyVRP did not return a capacity-feasible solution")

    routes: Routes = [[] for _ in range(problem.vehicle_count)]
    for route in result.best.routes():
        vehicle = int(route.vehicle_type())
        routes[vehicle] = [
            int(activity.idx)
            for activity in route
            if activity.is_client()
        ]

    validate_solution(problem, routes)
    return PyVRPBaselineResult(
        routes=routes,
        metrics=solution_metrics(problem, routes, config),
        solver_cost=int(result.cost()),
        iterations=limit,
        pyvrp_version=version("pyvrp"),
    )
