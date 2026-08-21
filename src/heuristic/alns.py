import random


class ALNSSolver:
    """Adaptive Large Neighborhood Search framework.

    Destroy and repair operators are separated from the search engine so new
    heuristics can be added without changing the optimization workflow.
    """

    def __init__(self, destroy_ops, repair_ops, iterations=1000):
        self.destroy_ops = destroy_ops
        self.repair_ops = repair_ops
        self.iterations = iterations
        self.operator_scores = {}

    def search(self, initial_solution, evaluate):
        current = initial_solution
        best = current
        best_cost = evaluate(best)

        for _ in range(self.iterations):
            destroy = random.choice(self.destroy_ops)
            repair = random.choice(self.repair_ops)

            partial, removed = destroy(current)
            candidate = repair(partial, removed)

            candidate_cost = evaluate(candidate)

            if candidate_cost < best_cost:
                best = candidate
                best_cost = candidate_cost
                current = candidate

        return best
