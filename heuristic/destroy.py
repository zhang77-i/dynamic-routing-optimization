import random


def random_removal(route, remove_count):
    route = list(route)
    if remove_count >= len(route):
        return [], route

    removed = random.sample(route, remove_count)
    remaining = [node for node in route if node not in removed]

    return remaining, removed


def worst_removal(route, costs, remove_count):
    ranked = sorted(
        zip(route, costs),
        key=lambda x: x[1],
        reverse=True,
    )

    removed = [node for node, _ in ranked[:remove_count]]
    remaining = [node for node in route if node not in removed]

    return remaining, removed
