from src.solver.base_solver import BaseRoutingSolver, RoutingSolution


class ALNSSolver(BaseRoutingSolver):
    """ALNS based routing solver implementation."""

    def __init__(self, search_engine):
        self.search_engine = search_engine

    def solve(self, instance):
        best_route = self.search_engine.search(instance)

        return RoutingSolution(
            routes=best_route.routes,
            distance=best_route.distance,
            vehicle_count=best_route.vehicle_count,
        )
