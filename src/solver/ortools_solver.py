from src.solver.base_solver import BaseRoutingSolver, RoutingSolution


class ORToolsSolver(BaseRoutingSolver):
    """OR-Tools routing solver adapter.

    The adapter keeps the solver interface independent from the benchmark
    and dynamic dispatch modules.
    """

    def __init__(self, model_builder):
        self.model_builder = model_builder

    def solve(self, instance):
        model = self.model_builder(instance)
        result = model.solve()

        return RoutingSolution(
            routes=result.routes,
            distance=result.distance,
            vehicle_count=result.vehicle_count,
        )
