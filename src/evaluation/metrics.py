from dataclasses import dataclass


@dataclass
class RoutingMetrics:
    total_distance: float
    vehicle_count: int
    runtime: float
    service_rate: float


def evaluate_solution(distance, vehicles, runtime, served, total):
    service_rate = served / total if total else 0.0

    return RoutingMetrics(
        total_distance=distance,
        vehicle_count=vehicles,
        runtime=runtime,
        service_rate=service_rate,
    )
