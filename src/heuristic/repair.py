def greedy_insertion(route, removed, cost_fn):
    """Greedy repair operator for ALNS.

    Insert removed nodes into positions with minimum incremental cost.
    """
    current = list(route)

    for node in removed:
        best_position = 0
        best_cost = float("inf")

        for idx in range(len(current) + 1):
            candidate = current[:idx] + [node] + current[idx:]
            cost = cost_fn(candidate)

            if cost < best_cost:
                best_cost = cost
                best_position = idx

        current.insert(best_position, node)

    return current


def regret_insertion(route, removed, cost_fn, regret_k=2):
    """Regret-k insertion repair strategy."""
    current = list(route)

    while removed:
        best_node = None
        best_position = None
        best_regret = -float("inf")

        for node in removed:
            costs = []
            for idx in range(len(current) + 1):
                candidate = current[:idx] + [node] + current[idx:]
                costs.append((cost_fn(candidate), idx))

            costs.sort(key=lambda x: x[0])
            regret = costs[min(regret_k, len(costs)-1)][0] - costs[0][0]

            if regret > best_regret:
                best_regret = regret
                best_node = node
                best_position = costs[0][1]

        current.insert(best_position, best_node)
        removed.remove(best_node)

    return current
