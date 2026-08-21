from copy import deepcopy


def alns(initial_solution, destroy, repair, iterations=100):
    current = deepcopy(initial_solution)
    best = deepcopy(current)

    for _ in range(iterations):
        removed, partial = destroy(current)
        candidate = repair(partial, removed)

        if objective(candidate) < objective(current):
            current = candidate

        if objective(current) < objective(best):
            best = deepcopy(current)

    return best


def objective(solution):
    return sum(
        abs(solution[i].x - solution[i + 1].x)
        for i in range(len(solution) - 1)
    )
