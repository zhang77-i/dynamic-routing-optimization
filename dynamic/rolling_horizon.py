from dataclasses import dataclass, field
from typing import List


@dataclass
class DynamicRoutingState:
    active_orders: List = field(default_factory=list)
    completed_orders: List = field(default_factory=list)


def update_order_pool(state: DynamicRoutingState, new_orders: List):
    state.active_orders.extend(new_orders)
    return state


def rolling_horizon_optimize(state: DynamicRoutingState, optimizer, execute_size=1):
    route = optimizer(state.active_orders)

    executed = route[:execute_size]
    remaining = route[execute_size:]

    state.completed_orders.extend(executed)
    state.active_orders = remaining

    return route, state
