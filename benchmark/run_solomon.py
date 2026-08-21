import time
from pathlib import Path

from src.data.solomon_loader import load_solomon_instance
from src.evaluation.metrics import evaluate_solution


class SolomonBenchmark:
    """Benchmark runner for Solomon VRPTW instances."""

    def __init__(self, solver):
        self.solver = solver

    def run(self, instance_path):
        customers = load_solomon_instance(instance_path)

        start = time.time()
        solution = self.solver.solve(customers)
        runtime = time.time() - start

        return evaluate_solution(
            distance=solution.distance,
            vehicles=solution.vehicle_count,
            runtime=runtime,
            served=len(customers),
            total=len(customers),
        )


if __name__ == "__main__":
    instance = Path("data/solomon/C101.txt")
    print(instance)
