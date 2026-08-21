import random


class ALNSOptimizer:
    """Adaptive Large Neighborhood Search framework.

    The optimizer alternates between destroy and repair operators to improve
    routing solutions.
    """

    def __init__(self, iterations=100):
        self.iterations = iterations

    def optimize(self, solution, destroy_operator, repair_operator):
        best = solution

        for _ in range(self.iterations):
            removed = destroy_operator(solution)
            candidate = repair_operator(removed)

            if self.accept(candidate, best):
                best = candidate

        return best

    def accept(self, candidate, current):
        return random.random() < 0.5
