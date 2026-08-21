from abc import ABC, abstractmethod


class BaseRoutingSolver(ABC):
    """Unified interface for routing optimization solvers."""

    @abstractmethod
    def solve(self, instance):
        raise NotImplementedError


class RoutingSolution:
    def __init__(self, routes, distance, vehicle_count):
        self.routes = routes
        self.distance = distance
        self.vehicle_count = vehicle_count
