from dataclasses import dataclass, field


@dataclass
class RoutingState:
    active_orders: list = field(default_factory=list)
    executed_orders: list = field(default_factory=list)


class RollingHorizonDispatcher:
    """Dynamic routing dispatcher using rolling horizon optimization.

    New orders can enter continuously. Previously executed decisions remain
    fixed while remaining tasks are re-optimized.
    """

    def __init__(self, solver):
        self.solver = solver
        self.state = RoutingState()

    def add_orders(self, orders):
        self.state.active_orders.extend(orders)

    def optimize(self):
        solution = self.solver.solve(self.state.active_orders)
        return solution

    def dispatch(self, completed_orders):
        self.state.executed_orders.extend(completed_orders)
        self.state.active_orders = [
            order for order in self.state.active_orders
            if order not in completed_orders
        ]
