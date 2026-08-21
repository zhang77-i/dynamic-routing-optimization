import random


def random_removal(route, remove_ratio=0.2):
    """Random destroy operator for ALNS."""
    if not route:
        return [], []

    size = max(1, int(len(route) * remove_ratio))
    removed = random.sample(route, min(size, len(route)))
    remaining = [node for node in route if node not in removed]

    return remaining, removed


def worst_removal(route, scores, remove_ratio=0.2):
    """Remove nodes with highest contribution scores."""
    size = max(1, int(len(route) * remove_ratio))
    ranked = sorted(route, key=lambda x: scores.get(x, 0), reverse=True)
    removed = ranked[:size]
    remaining = [node for node in route if node not in removed]

    return remaining, removed
