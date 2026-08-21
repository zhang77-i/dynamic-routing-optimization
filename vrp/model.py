from dataclasses import dataclass
from typing import List


@dataclass
class Customer:
    index: int
    x: float
    y: float
    demand: float


@dataclass
class Vehicle:
    index: int
    capacity: float


def euclidean_distance(a: Customer, b: Customer) -> float:
    return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5


def route_cost(route: List[Customer]) -> float:
    if len(route) < 2:
        return 0.0

    return sum(
        euclidean_distance(route[i], route[i + 1])
        for i in range(len(route) - 1)
    )
