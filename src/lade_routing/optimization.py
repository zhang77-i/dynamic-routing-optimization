from __future__ import annotations

import copy
import json
import math
import os
import sysconfig
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

_ORTOOLS_DLL_DIRECTORY = None
if os.name == "nt":
    _ortools_dll_path = (
        Path(sysconfig.get_paths()["purelib"]) / "ortools" / ".libs"
    )
    if _ortools_dll_path.exists():
        _ORTOOLS_DLL_DIRECTORY = os.add_dll_directory(
            str(_ortools_dll_path)
        )

from ortools.sat.python import cp_model
from scipy.spatial.distance import cdist

from .config import ProjectConfig
from .cpp_core import CPP_CORE

Routes = list[list[int]]


@dataclass(frozen=True)
class RoutingProblem:
    instance_id: str
    order_ids: np.ndarray
    points: np.ndarray
    release_seconds: np.ndarray
    due_seconds: np.ndarray
    courier_ids: np.ndarray
    starts: np.ndarray
    capacity: int
    order_distance: np.ndarray
    start_distance: np.ndarray

    @property
    def order_count(self) -> int:
        return len(self.order_ids)

    @property
    def vehicle_count(self) -> int:
        return len(self.courier_ids)


@dataclass(frozen=True)
class ALNSResult:
    routes: Routes
    distance_m: float
    objective_value: float
    synthetic_sla_late_rate: float
    total_lateness_minutes: float
    iterations: int
    destroy_weights: dict[str, float]
    repair_weights: dict[str, float]


@dataclass(frozen=True)
class RoutingMetrics:
    distance_m: float
    objective_value: float
    synthetic_sla_late_rate: float
    total_lateness_minutes: float
    workload_std: float


def load_problem(path: str | Path, config: ProjectConfig) -> RoutingProblem:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    orders = payload["orders"]
    couriers = payload["couriers"]
    points = np.array(
        [[order["destination_x"], order["destination_y"]] for order in orders],
        dtype=np.float64,
    )
    starts = np.array(
        [[courier["start_x"], courier["start_y"]] for courier in couriers],
        dtype=np.float64,
    )
    release = np.array(
        [order["release_seconds"] for order in orders],
        dtype=np.float64,
    )
    sla = float(config.processing["synthetic_sla_seconds"])
    capacity = max(
        1,
        int(
            math.ceil(
                len(orders)
                / max(len(couriers), 1)
                * float(config.optimization["capacity_factor"])
            )
        ),
    )
    return RoutingProblem(
        instance_id=payload["instance_id"],
        order_ids=np.array([order["order_id"] for order in orders], dtype=np.int64),
        points=points,
        release_seconds=release,
        due_seconds=release + sla,
        courier_ids=np.array(
            [courier["courier_id"] for courier in couriers],
            dtype=np.int64,
        ),
        starts=starts,
        capacity=capacity,
        order_distance=cdist(points, points, metric="euclidean"),
        start_distance=cdist(starts, points, metric="euclidean"),
    )


def route_distance(problem: RoutingProblem, route: list[int], vehicle: int) -> float:
    if not route:
        return 0.0
    if CPP_CORE.available and CPP_CORE.enabled:
        return CPP_CORE.route_distance(
            problem.start_distance,
            problem.order_distance,
            vehicle,
            route,
        )
    distance = float(problem.start_distance[vehicle, route[0]])
    if len(route) > 1:
        distance += float(
            problem.order_distance[
                np.asarray(route[:-1], dtype=int),
                np.asarray(route[1:], dtype=int),
            ].sum()
        )
    return distance


def solution_distance(problem: RoutingProblem, routes: Routes) -> float:
    return float(
        sum(
            route_distance(problem, route, vehicle)
            for vehicle, route in enumerate(routes)
        )
    )


def route_completion_times(
    problem: RoutingProblem,
    route: list[int],
    vehicle: int,
    speed_mps: float,
    service_seconds: float,
) -> np.ndarray:
    if not route:
        return np.empty(0, dtype=np.float64)
    completion = np.empty(len(route), dtype=np.float64)
    current_time = 0.0
    previous_order: int | None = None
    for position, order in enumerate(route):
        travel_distance = (
            problem.start_distance[vehicle, order]
            if previous_order is None
            else problem.order_distance[previous_order, order]
        )
        arrival = current_time + float(travel_distance) / speed_mps
        service_start = max(arrival, float(problem.release_seconds[order]))
        current_time = service_start + service_seconds
        completion[position] = current_time
        previous_order = order
    return completion


def solution_metrics(
    problem: RoutingProblem,
    routes: Routes,
    config: ProjectConfig,
) -> RoutingMetrics:
    speed_mps = float(config.processing["assumed_speed_kph"]) / 3.6
    service_seconds = float(config.processing["service_time_seconds"])
    late_orders = 0
    total_lateness_seconds = 0.0
    for vehicle, route in enumerate(routes):
        completion = route_completion_times(
            problem,
            route,
            vehicle,
            speed_mps,
            service_seconds,
        )
        if not route:
            continue
        due = problem.due_seconds[np.asarray(route, dtype=int)]
        lateness = np.maximum(completion - due, 0.0)
        late_orders += int(np.count_nonzero(lateness))
        total_lateness_seconds += float(lateness.sum())

    distance_m = solution_distance(problem, routes)
    late_penalty = float(
        config.optimization.get("late_penalty_meters_per_second", 1.0)
    )
    workload_penalty = float(
        config.optimization.get("workload_std_penalty_meters", 100.0)
    )
    workload_std = float(np.std([len(route) for route in routes]))
    return RoutingMetrics(
        distance_m=distance_m,
        objective_value=(
            distance_m
            + late_penalty * total_lateness_seconds
            + workload_penalty * workload_std
        ),
        synthetic_sla_late_rate=late_orders / max(problem.order_count, 1),
        total_lateness_minutes=total_lateness_seconds / 60.0,
        workload_std=workload_std,
    )


def validate_solution(
    problem: RoutingProblem,
    routes: Routes,
    *,
    enforce_capacity: bool = True,
) -> None:
    assigned = [order for route in routes for order in route]
    if len(assigned) != problem.order_count:
        raise ValueError(
            f"Expected {problem.order_count} assigned orders, got {len(assigned)}"
        )
    if sorted(assigned) != list(range(problem.order_count)):
        raise ValueError("Orders are duplicated or missing")
    if enforce_capacity and any(len(route) > problem.capacity for route in routes):
        raise ValueError("Route capacity exceeded")


def insertion_delta(
    problem: RoutingProblem,
    route: list[int],
    vehicle: int,
    order: int,
    position: int,
) -> float:
    if not route:
        return float(problem.start_distance[vehicle, order])
    if position == 0:
        return float(
            problem.start_distance[vehicle, order]
            + problem.order_distance[order, route[0]]
            - problem.start_distance[vehicle, route[0]]
        )
    previous = route[position - 1]
    if position == len(route):
        return float(problem.order_distance[previous, order])
    following = route[position]
    return float(
        problem.order_distance[previous, order]
        + problem.order_distance[order, following]
        - problem.order_distance[previous, following]
    )


def best_insertions(
    problem: RoutingProblem,
    routes: Routes,
    order: int,
) -> list[tuple[float, int, int]]:
    if CPP_CORE.available and CPP_CORE.enabled:
        return CPP_CORE.all_insertion_options(
            problem.start_distance,
            problem.order_distance,
            routes,
            problem.capacity,
            order,
        )
    options: list[tuple[float, int, int]] = []
    for vehicle, route in enumerate(routes):
        if len(route) >= problem.capacity:
            continue
        for position in range(len(route) + 1):
            options.append(
                (
                    insertion_delta(
                        problem,
                        route,
                        vehicle,
                        order,
                        position,
                    ),
                    vehicle,
                    position,
                )
            )
    options.sort(key=lambda value: (value[0], value[1], value[2]))
    return options


def repair_solution(
    problem: RoutingProblem,
    routes: Routes,
    removed: list[int],
    regret_k: int,
) -> Routes:
    candidate = copy.deepcopy(routes)
    pending = list(removed)
    while pending:
        scored = []
        for order in pending:
            options = best_insertions(problem, candidate, order)
            if not options:
                raise ValueError("No capacity-feasible insertion exists")
            if regret_k <= 1:
                score = -options[0][0]
            else:
                available = options[: min(regret_k, len(options))]
                score = sum(option[0] - options[0][0] for option in available[1:])
            scored.append((score, -options[0][0], order, options[0]))
        _, _, chosen, insertion = max(scored)
        _, vehicle, position = insertion
        candidate[vehicle].insert(position, chosen)
        pending.remove(chosen)
    return candidate


def greedy_initial_solution(problem: RoutingProblem) -> Routes:
    routes: Routes = [[] for _ in range(problem.vehicle_count)]
    order_sequence = np.argsort(problem.release_seconds, kind="stable").tolist()
    return repair_solution(problem, routes, order_sequence, regret_k=2)


def _removal_saving(
    problem: RoutingProblem,
    route: list[int],
    vehicle: int,
    position: int,
) -> float:
    order = route[position]
    previous_distance = (
        problem.start_distance[vehicle, order]
        if position == 0
        else problem.order_distance[route[position - 1], order]
    )
    next_distance = (
        0.0
        if position == len(route) - 1
        else problem.order_distance[order, route[position + 1]]
    )
    bypass = 0.0
    if position < len(route) - 1:
        bypass = (
            problem.start_distance[vehicle, route[position + 1]]
            if position == 0
            else problem.order_distance[route[position - 1], route[position + 1]]
        )
    return float(previous_distance + next_distance - bypass)


def destroy_random(
    problem: RoutingProblem,
    routes: Routes,
    count: int,
    rng: np.random.Generator,
) -> tuple[Routes, list[int]]:
    assigned = np.array([order for route in routes for order in route], dtype=int)
    removed = rng.choice(assigned, size=min(count, len(assigned)), replace=False).tolist()
    removed_set = set(removed)
    return [
        [order for order in route if order not in removed_set]
        for route in routes
    ], removed


def destroy_worst(
    problem: RoutingProblem,
    routes: Routes,
    count: int,
    rng: np.random.Generator,
) -> tuple[Routes, list[int]]:
    savings = []
    for vehicle, route in enumerate(routes):
        for position, order in enumerate(route):
            savings.append(
                (
                    _removal_saving(problem, route, vehicle, position),
                    float(rng.random()) * 1e-6,
                    order,
                )
            )
    savings.sort(reverse=True)
    removed = [row[2] for row in savings[:count]]
    removed_set = set(removed)
    return [
        [order for order in route if order not in removed_set]
        for route in routes
    ], removed


def destroy_related(
    problem: RoutingProblem,
    routes: Routes,
    count: int,
    rng: np.random.Generator,
) -> tuple[Routes, list[int]]:
    assigned = [order for route in routes for order in route]
    seed = int(rng.choice(assigned))
    spatial = problem.order_distance[seed]
    time_delta = np.abs(
        problem.release_seconds - problem.release_seconds[seed]
    )
    positive_spatial = spatial[spatial > 0]
    positive_time = time_delta[time_delta > 0]
    spatial_scale = (
        max(float(np.median(positive_spatial)), 1.0)
        if positive_spatial.size
        else 1.0
    )
    time_scale = (
        max(float(np.median(positive_time)), 1.0)
        if positive_time.size
        else 1.0
    )
    relatedness = spatial / spatial_scale + 0.5 * time_delta / time_scale
    removed = [
        int(order)
        for order in np.argsort(relatedness)
        if int(order) in set(assigned)
    ][:count]
    removed_set = set(removed)
    return [
        [order for order in route if order not in removed_set]
        for route in routes
    ], removed


def destroy_route(
    problem: RoutingProblem,
    routes: Routes,
    count: int,
    rng: np.random.Generator,
) -> tuple[Routes, list[int]]:
    nonempty = [index for index, route in enumerate(routes) if route]
    selected = int(rng.choice(nonempty))
    route = routes[selected]
    if len(route) <= count:
        removed = list(route)
    else:
        start = int(rng.integers(0, len(route) - count + 1))
        removed = route[start : start + count]
    removed_set = set(removed)
    return [
        [order for order in current if order not in removed_set]
        for current in routes
    ], removed


def two_opt_solution(problem: RoutingProblem, routes: Routes) -> Routes:
    improved = copy.deepcopy(routes)
    if CPP_CORE.available and CPP_CORE.enabled:
        for vehicle, route in enumerate(improved):
            optimized, _ = CPP_CORE.two_opt(
                problem.start_distance,
                problem.order_distance,
                vehicle,
                route,
            )
            route[:] = optimized
        return improved
    for vehicle, route in enumerate(improved):
        if len(route) < 4:
            continue
        current_cost = route_distance(problem, route, vehicle)
        changed = True
        while changed:
            changed = False
            for left in range(len(route) - 2):
                for right in range(left + 2, len(route) + 1):
                    candidate = (
                        route[:left]
                        + list(reversed(route[left:right]))
                        + route[right:]
                    )
                    candidate_cost = route_distance(problem, candidate, vehicle)
                    if candidate_cost + 1e-9 < current_cost:
                        route[:] = candidate
                        current_cost = candidate_cost
                        changed = True
                        break
                if changed:
                    break
    return improved


class ALNSSolver:
    def __init__(self, problem: RoutingProblem, config: ProjectConfig):
        self.problem = problem
        self.config = config
        self.rng = np.random.default_rng(config.random_seed)
        self.destroy_operators = {
            "random": destroy_random,
            "worst": destroy_worst,
            "shaw_related": destroy_related,
            "route_segment": destroy_route,
        }
        self.repair_operators = {
            "greedy": 1,
            "regret_2": 2,
            "regret_3": 3,
        }

    def solve(self, iterations: int | None = None) -> ALNSResult:
        iterations = (
            int(iterations)
            if iterations is not None
            else int(self.config.optimization["alns_iterations"])
        )
        fraction = float(self.config.optimization["alns_removal_fraction"])
        reaction = float(self.config.optimization["alns_reaction_factor"])
        cooling = float(self.config.optimization["alns_cooling_rate"])
        segment_size = int(self.config.optimization["alns_segment_size"])
        removal_count = max(2, int(math.ceil(self.problem.order_count * fraction)))

        current = two_opt_solution(
            self.problem,
            greedy_initial_solution(self.problem),
        )
        current_cost = solution_metrics(
            self.problem,
            current,
            self.config,
        ).objective_value
        best = copy.deepcopy(current)
        best_cost = current_cost
        temperature = max(current_cost * 0.05, 1.0)

        destroy_weights = {name: 1.0 for name in self.destroy_operators}
        repair_weights = {name: 1.0 for name in self.repair_operators}
        destroy_score = {name: 0.0 for name in self.destroy_operators}
        repair_score = {name: 0.0 for name in self.repair_operators}
        destroy_use = {name: 0 for name in self.destroy_operators}
        repair_use = {name: 0 for name in self.repair_operators}

        for iteration in range(1, iterations + 1):
            destroy_name = self._weighted_choice(destroy_weights)
            repair_name = self._weighted_choice(repair_weights)
            destroy_use[destroy_name] += 1
            repair_use[repair_name] += 1

            partial, removed = self.destroy_operators[destroy_name](
                self.problem,
                current,
                removal_count,
                self.rng,
            )
            candidate = repair_solution(
                self.problem,
                partial,
                removed,
                regret_k=self.repair_operators[repair_name],
            )
            if iteration % 10 == 0:
                candidate = two_opt_solution(self.problem, candidate)
            candidate_cost = solution_metrics(
                self.problem,
                candidate,
                self.config,
            ).objective_value
            delta = candidate_cost - current_cost
            accepted = (
                delta <= 0
                or self.rng.random() < math.exp(-delta / max(temperature, 1e-12))
            )
            score = 0.0
            if candidate_cost + 1e-9 < best_cost:
                best = copy.deepcopy(candidate)
                best_cost = candidate_cost
                score = 10.0
            elif accepted and candidate_cost + 1e-9 < current_cost:
                score = 5.0
            elif accepted:
                score = 1.0
            if accepted:
                current = candidate
                current_cost = candidate_cost
            destroy_score[destroy_name] += score
            repair_score[repair_name] += score
            temperature *= cooling

            if iteration % segment_size == 0:
                self._update_weights(
                    destroy_weights,
                    destroy_score,
                    destroy_use,
                    reaction,
                )
                self._update_weights(
                    repair_weights,
                    repair_score,
                    repair_use,
                    reaction,
                )

        best = two_opt_solution(self.problem, best)
        validate_solution(self.problem, best)
        metrics = solution_metrics(self.problem, best, self.config)
        return ALNSResult(
            routes=best,
            distance_m=metrics.distance_m,
            objective_value=metrics.objective_value,
            synthetic_sla_late_rate=metrics.synthetic_sla_late_rate,
            total_lateness_minutes=metrics.total_lateness_minutes,
            iterations=iterations,
            destroy_weights=destroy_weights,
            repair_weights=repair_weights,
        )

    def _weighted_choice(self, weights: dict[str, float]) -> str:
        names = list(weights)
        values = np.array([weights[name] for name in names], dtype=float)
        values /= values.sum()
        return str(self.rng.choice(names, p=values))

    @staticmethod
    def _update_weights(
        weights: dict[str, float],
        scores: dict[str, float],
        uses: dict[str, int],
        reaction: float,
    ) -> None:
        for name in weights:
            if uses[name] > 0:
                performance = scores[name] / uses[name]
                weights[name] = max(
                    (1.0 - reaction) * weights[name]
                    + reaction * performance,
                    0.05,
                )
            scores[name] = 0.0
            uses[name] = 0


def _cp_sat_assignment(
    problem: RoutingProblem,
    time_limit_seconds: float,
    workers: int,
) -> tuple[Routes | None, str]:
    model = cp_model.CpModel()
    assignment = {
        (vehicle, order): model.new_bool_var(f"a_{vehicle}_{order}")
        for vehicle in range(problem.vehicle_count)
        for order in range(problem.order_count)
    }
    for order in range(problem.order_count):
        model.add_exactly_one(
            assignment[vehicle, order]
            for vehicle in range(problem.vehicle_count)
        )

    loads = []
    for vehicle in range(problem.vehicle_count):
        load = model.new_int_var(0, problem.capacity, f"load_{vehicle}")
        model.add(
            load
            == sum(
                assignment[vehicle, order]
                for order in range(problem.order_count)
            )
        )
        loads.append(load)

    max_load = model.new_int_var(0, problem.capacity, "max_load")
    min_load = model.new_int_var(0, problem.capacity, "min_load")
    model.add_max_equality(max_load, loads)
    model.add_min_equality(min_load, loads)
    distance_cost = sum(
        int(round(float(problem.start_distance[vehicle, order])))
        * assignment[vehicle, order]
        for vehicle in range(problem.vehicle_count)
        for order in range(problem.order_count)
    )
    model.minimize(distance_cost + 250 * (max_load - min_load))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(float(time_limit_seconds), 0.2)
    solver.parameters.num_search_workers = max(int(workers), 1)
    solver.parameters.random_seed = 42
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None, solver.status_name(status).lower()

    routes: Routes = []
    for vehicle in range(problem.vehicle_count):
        routes.append(
            [
                order
                for order in range(problem.order_count)
                if solver.boolean_value(assignment[vehicle, order])
            ]
        )
    return routes, solver.status_name(status).lower()


def _nearest_neighbor_order(
    problem: RoutingProblem,
    vehicle: int,
    assigned: list[int],
) -> list[int]:
    remaining = set(assigned)
    route: list[int] = []
    current: int | None = None
    while remaining:
        if current is None:
            chosen = min(
                remaining,
                key=lambda order: (
                    problem.start_distance[vehicle, order],
                    order,
                ),
            )
        else:
            chosen = min(
                remaining,
                key=lambda order: (
                    problem.order_distance[current, order],
                    order,
                ),
            )
        route.append(int(chosen))
        remaining.remove(chosen)
        current = int(chosen)
    return route


def _cp_sat_open_route(
    problem: RoutingProblem,
    vehicle: int,
    assigned: list[int],
    time_limit_seconds: float,
    workers: int,
    late_penalty_meters_per_second: float,
    speed_mps: float,
    service_seconds: int,
) -> tuple[list[int], str]:
    if len(assigned) <= 1:
        return list(assigned), "optimal"

    model = cp_model.CpModel()
    start_node = 0
    sink_node = len(assigned) + 1
    order_nodes = list(range(1, sink_node))
    local_to_global = {
        local: int(assigned[local - 1])
        for local in order_nodes
    }
    arc_vars: dict[tuple[int, int], cp_model.IntVar] = {}
    circuit_arcs: list[tuple[int, int, cp_model.IntVar]] = []

    def add_arc(source: int, target: int, name: str) -> None:
        variable = model.new_bool_var(name)
        arc_vars[source, target] = variable
        circuit_arcs.append((source, target, variable))

    for target in order_nodes:
        add_arc(start_node, target, f"x_start_{target}")
    for source in order_nodes:
        for target in order_nodes:
            if source != target:
                add_arc(source, target, f"x_{source}_{target}")
        add_arc(source, sink_node, f"x_{source}_sink")
    sink_to_start = model.new_bool_var("x_sink_start")
    model.add(sink_to_start == 1)
    arc_vars[sink_node, start_node] = sink_to_start
    circuit_arcs.append((sink_node, start_node, sink_to_start))
    model.add_circuit(circuit_arcs)

    max_due = int(max(problem.due_seconds[assigned]))
    horizon = max_due + 24 * 3600
    big_m = horizon + 24 * 3600
    service_start: dict[int, cp_model.IntVar] = {}
    lateness: dict[int, cp_model.IntVar] = {}
    for local in order_nodes:
        order = local_to_global[local]
        release = int(math.floor(problem.release_seconds[order]))
        due = int(math.ceil(problem.due_seconds[order]))
        service_start[local] = model.new_int_var(
            max(release, 0),
            horizon,
            f"service_start_{local}",
        )
        lateness[local] = model.new_int_var(0, horizon, f"late_{local}")
        model.add(
            lateness[local]
            >= service_start[local] + service_seconds - due
        )
        travel = int(
            math.ceil(problem.start_distance[vehicle, order] / speed_mps)
        )
        model.add(
            service_start[local]
            >= travel - big_m * (1 - arc_vars[start_node, local])
        )

    for source in order_nodes:
        source_order = local_to_global[source]
        for target in order_nodes:
            if source == target:
                continue
            target_order = local_to_global[target]
            travel = int(
                math.ceil(
                    problem.order_distance[source_order, target_order]
                    / speed_mps
                )
            )
            model.add(
                service_start[target]
                >= service_start[source]
                + service_seconds
                + travel
                - big_m * (1 - arc_vars[source, target])
            )

    distance_terms = []
    for (source, target), variable in arc_vars.items():
        if source == sink_node or target == sink_node:
            distance = 0
        elif source == start_node:
            distance = int(
                round(
                    float(
                        problem.start_distance[
                            vehicle,
                            local_to_global[target],
                        ]
                    )
                )
            )
        else:
            distance = int(
                round(
                    float(
                        problem.order_distance[
                            local_to_global[source],
                            local_to_global[target],
                        ]
                    )
                )
            )
        distance_terms.append(distance * variable)
    late_weight = max(int(round(late_penalty_meters_per_second)), 1)
    model.minimize(
        sum(distance_terms)
        + late_weight * sum(lateness.values())
    )

    hint_route = _nearest_neighbor_order(problem, vehicle, assigned)
    global_to_local = {
        global_order: local
        for local, global_order in local_to_global.items()
    }
    hint_nodes = [start_node] + [
        global_to_local[order] for order in hint_route
    ] + [sink_node, start_node]
    hinted_arcs = set(zip(hint_nodes[:-1], hint_nodes[1:]))
    for arc, variable in arc_vars.items():
        model.add_hint(variable, int(arc in hinted_arcs))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(float(time_limit_seconds), 0.2)
    solver.parameters.num_search_workers = max(int(workers), 1)
    solver.parameters.random_seed = 42 + vehicle
    status = solver.solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return hint_route, f"fallback_{solver.status_name(status).lower()}"

    route: list[int] = []
    current = start_node
    for _ in range(len(assigned) + 1):
        following = [
            target
            for (source, target), variable in arc_vars.items()
            if source == current and solver.boolean_value(variable)
        ]
        if len(following) != 1:
            return hint_route, "fallback_invalid_successor"
        current = following[0]
        if current == sink_node:
            break
        route.append(local_to_global[current])
    if len(route) != len(assigned):
        return hint_route, "fallback_incomplete_route"
    return route, solver.status_name(status).lower()


def solve_cp_sat(
    problem: RoutingProblem,
    config: ProjectConfig,
) -> tuple[Routes | None, RoutingMetrics | None, str]:
    time_limit_seconds = float(
        config.optimization["cp_sat_time_limit_seconds"]
    )
    workers = int(config.optimization.get("cp_sat_num_workers", 4))
    late_penalty = float(
        config.optimization.get("late_penalty_meters_per_second", 1.0)
    )
    speed_mps = float(config.processing["assumed_speed_kph"]) / 3.6
    service_seconds = int(config.processing["service_time_seconds"])
    assigned_routes, assignment_status = _cp_sat_assignment(
        problem,
        time_limit_seconds=max(time_limit_seconds * 0.2, 0.5),
        workers=workers,
    )
    if assigned_routes is None:
        return None, None, f"assignment_{assignment_status}"

    nonempty = max(sum(bool(route) for route in assigned_routes), 1)
    route_time_limit = max(time_limit_seconds * 0.8 / nonempty, 0.3)
    routes: Routes = []
    route_statuses: list[str] = []
    for vehicle, assigned in enumerate(assigned_routes):
        route, route_status = _cp_sat_open_route(
            problem,
            vehicle,
            assigned,
            time_limit_seconds=route_time_limit,
            workers=workers,
            late_penalty_meters_per_second=late_penalty,
            speed_mps=speed_mps,
            service_seconds=service_seconds,
        )
        routes.append(route)
        route_statuses.append(route_status)

    validate_solution(problem, routes)
    metrics = solution_metrics(problem, routes, config)
    fallback_count = sum(status.startswith("fallback") for status in route_statuses)
    status = (
        f"{assignment_status};route_fallbacks={fallback_count}/{nonempty}"
    )
    return routes, metrics, status


def dynamic_online_greedy(
    problem: RoutingProblem,
    config: ProjectConfig,
) -> dict:
    speed_mps = float(config.processing["assumed_speed_kph"]) / 3.6
    service_seconds = float(config.processing["service_time_seconds"])
    interval = int(config.processing["dispatch_interval_seconds"])
    position = problem.starts.copy()
    available = np.zeros(problem.vehicle_count, dtype=np.float64)
    workload = np.zeros(problem.vehicle_count, dtype=np.int64)
    routes: Routes = [[] for _ in range(problem.vehicle_count)]
    total_distance = 0.0
    late = 0
    total_lateness_seconds = 0.0
    completion = np.zeros(problem.order_count, dtype=np.float64)

    batches = (
        problem.release_seconds.astype(int) // interval * interval
    )
    for batch in np.unique(batches):
        released = np.flatnonzero(batches == batch)
        released = released[np.argsort(problem.release_seconds[released], kind="stable")]
        for order in released:
            travel = np.linalg.norm(position - problem.points[order], axis=1)
            start_time = np.maximum(available, problem.release_seconds[order])
            finish = start_time + travel / speed_mps + service_seconds
            lateness = np.maximum(finish - problem.due_seconds[order], 0.0)
            score = finish + 2.0 * lateness + workload * service_seconds * 0.1
            vehicle = int(np.argmin(score))
            total_distance += float(travel[vehicle])
            available[vehicle] = finish[vehicle]
            completion[order] = finish[vehicle]
            position[vehicle] = problem.points[order]
            workload[vehicle] += 1
            routes[vehicle].append(int(order))
            late += int(finish[vehicle] > problem.due_seconds[order])
            total_lateness_seconds += max(
                float(finish[vehicle] - problem.due_seconds[order]),
                0.0,
            )

    validate_solution(problem, routes)
    workload_std = float(workload.std())
    objective_value = (
        total_distance
        + float(
            config.optimization.get(
                "late_penalty_meters_per_second",
                1.0,
            )
        )
        * total_lateness_seconds
        + float(
            config.optimization.get(
                "workload_std_penalty_meters",
                100.0,
            )
        )
        * workload_std
    )
    return {
        "routes": routes,
        "distance_m": total_distance,
        "objective_value": objective_value,
        "synthetic_sla_late_rate": late / max(problem.order_count, 1),
        "total_lateness_minutes": total_lateness_seconds / 60.0,
        "workload_std": workload_std,
        "max_completion_seconds": float(completion.max()),
    }


def _dynamic_subproblem(
    problem: RoutingProblem,
    pending_orders: list[int],
    available_vehicles: list[int],
    current_positions: np.ndarray,
    capacity_factor: float,
    current_time: float,
) -> RoutingProblem:
    order_index = np.asarray(pending_orders, dtype=int)
    vehicle_index = np.asarray(available_vehicles, dtype=int)
    points = problem.points[order_index]
    starts = current_positions[vehicle_index]
    capacity = max(
        1,
        int(
            math.ceil(
                len(pending_orders)
                / max(len(available_vehicles), 1)
                * capacity_factor
            )
        ),
    )
    return RoutingProblem(
        instance_id=f"{problem.instance_id}__rolling",
        order_ids=problem.order_ids[order_index],
        points=points,
        release_seconds=np.maximum(
            problem.release_seconds[order_index],
            current_time,
        ),
        due_seconds=problem.due_seconds[order_index],
        courier_ids=problem.courier_ids[vehicle_index],
        starts=starts,
        capacity=capacity,
        order_distance=problem.order_distance[np.ix_(order_index, order_index)],
        start_distance=cdist(starts, points, metric="euclidean"),
    )


def dynamic_rolling_alns(
    problem: RoutingProblem,
    config: ProjectConfig,
) -> dict:
    speed_mps = float(config.processing["assumed_speed_kph"]) / 3.6
    service_seconds = float(config.processing["service_time_seconds"])
    interval = int(config.processing["dispatch_interval_seconds"])
    capacity_factor = float(config.optimization["capacity_factor"])
    iterations = int(config.optimization["rolling_alns_iterations"])
    current_positions = problem.starts.copy()
    available_time = np.zeros(problem.vehicle_count, dtype=np.float64)
    workloads = np.zeros(problem.vehicle_count, dtype=np.int64)
    completion = np.zeros(problem.order_count, dtype=np.float64)
    routes: Routes = [[] for _ in range(problem.vehicle_count)]
    pending: list[int] = []
    assigned = np.zeros(problem.order_count, dtype=bool)
    released = np.zeros(problem.order_count, dtype=bool)
    total_distance = 0.0
    total_lateness_seconds = 0.0
    replans = 0
    optimization_seconds = 0.0

    current_time = (
        math.floor(float(problem.release_seconds.min()) / interval) * interval
    )
    final_release = float(problem.release_seconds.max())
    max_steps = int(math.ceil((final_release + 48 * 3600) / interval)) + 1
    steps = 0

    while not bool(assigned.all()):
        newly_released = np.flatnonzero(
            (~released) & (problem.release_seconds <= current_time)
        )
        for order in newly_released.tolist():
            pending.append(int(order))
            released[order] = True
        pending.sort(
            key=lambda order: (
                problem.due_seconds[order],
                problem.release_seconds[order],
                order,
            )
        )
        available_vehicles = np.flatnonzero(
            available_time <= current_time + 1e-9
        ).tolist()

        if pending and available_vehicles:
            subproblem = _dynamic_subproblem(
                problem,
                pending,
                available_vehicles,
                current_positions,
                capacity_factor,
                current_time,
            )
            started = time.perf_counter()
            plan = ALNSSolver(subproblem, config).solve(iterations=iterations)
            optimization_seconds += time.perf_counter() - started
            replans += 1

            committed: list[int] = []
            for local_vehicle, route in enumerate(plan.routes):
                if not route:
                    continue
                local_order = int(route[0])
                original_order = int(pending[local_order])
                vehicle = int(available_vehicles[local_vehicle])
                travel_distance = float(
                    np.linalg.norm(
                        current_positions[vehicle]
                        - problem.points[original_order]
                    )
                )
                start_service = max(
                    current_time + travel_distance / speed_mps,
                    float(problem.release_seconds[original_order]),
                )
                finish = start_service + service_seconds
                routes[vehicle].append(original_order)
                current_positions[vehicle] = problem.points[original_order]
                available_time[vehicle] = finish
                completion[original_order] = finish
                workloads[vehicle] += 1
                assigned[original_order] = True
                committed.append(original_order)
                total_distance += travel_distance
                total_lateness_seconds += max(
                    finish - float(problem.due_seconds[original_order]),
                    0.0,
                )
            committed_set = set(committed)
            pending = [
                order for order in pending if order not in committed_set
            ]

        current_time += interval
        steps += 1
        if steps > max_steps:
            raise RuntimeError("Rolling-horizon replay exceeded safety horizon")

    validate_solution(problem, routes, enforce_capacity=False)
    workload_std = float(workloads.std())
    late_rate = float(
        np.mean(completion > problem.due_seconds)
    )
    objective_value = (
        total_distance
        + float(
            config.optimization.get(
                "late_penalty_meters_per_second",
                1.0,
            )
        )
        * total_lateness_seconds
        + float(
            config.optimization.get(
                "workload_std_penalty_meters",
                100.0,
            )
        )
        * workload_std
    )
    return {
        "routes": routes,
        "distance_m": total_distance,
        "objective_value": objective_value,
        "synthetic_sla_late_rate": late_rate,
        "total_lateness_minutes": total_lateness_seconds / 60.0,
        "workload_std": workload_std,
        "max_completion_seconds": float(completion.max()),
        "replans": replans,
        "optimization_seconds": optimization_seconds,
    }


def serialize_routes(problem: RoutingProblem, routes: Routes) -> list[dict]:
    return [
        {
            "courier_id": int(problem.courier_ids[vehicle]),
            "order_ids": problem.order_ids[np.asarray(route, dtype=int)].astype(int).tolist(),
            "orders": len(route),
            "distance_m": route_distance(problem, route, vehicle),
        }
        for vehicle, route in enumerate(routes)
    ]
