import numpy as np

from lade_routing.routing import nearest_neighbor_distance


def test_nearest_neighbor_route() -> None:
    points = np.array([[10.0, 0.0], [1.0, 0.0], [3.0, 0.0]])
    order, distance = nearest_neighbor_distance(points, np.array([0.0, 0.0]))
    assert order.tolist() == [1, 2, 0]
    assert distance == 10.0
