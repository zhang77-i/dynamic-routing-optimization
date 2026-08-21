from src.solver.base_solver import RoutingSolution


def test_routing_solution_structure():
    solution = RoutingSolution(
        routes=[[0, 1, 2]],
        distance=10.0,
        vehicle_count=1,
    )

    assert solution.distance >= 0
    assert solution.vehicle_count > 0
    assert len(solution.routes) > 0
