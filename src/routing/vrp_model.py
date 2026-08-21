from dataclasses import dataclass


@dataclass
class VRPNode:
    node_id: int
    demand: float = 0.0


class DynamicVRPModel:
    """Basic VRP model interface.

    This module defines the optimization problem layer. A solver such as
    OR-Tools can be connected to this interface.
    """

    def __init__(self, nodes, vehicle_capacity):
        self.nodes = nodes
        self.vehicle_capacity = vehicle_capacity

    def capacity_feasible(self, route):
        total = sum(node.demand for node in route)
        return total <= self.vehicle_capacity
