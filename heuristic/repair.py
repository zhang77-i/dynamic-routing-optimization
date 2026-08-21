from copy import deepcopy


def insertion_cost(route, customer, position):
    before = route[position - 1]
    after = route[position]
    return (
        abs(before.x - customer.x)
        + abs(customer.x - after.x)
        - abs(before.x - after.x)
    )


def greedy_insertion(route, removed_customers):
    solution = deepcopy(route)

    for customer in removed_customers:
        best_position = 1
        best_cost = float('inf')

        for position in range(1, len(solution)):
            cost = insertion_cost(solution, customer, position)
            if cost < best_cost:
                best_cost = cost
                best_position = position

        solution.insert(best_position, customer)

    return solution
