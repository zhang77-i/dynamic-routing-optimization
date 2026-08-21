from dataclasses import dataclass


@dataclass
class Order:
    order_id: int
    location: tuple
    demand: float
    release_time: int


class DynamicOrderStream:
    """Simulate online order arrivals for dynamic routing experiments."""

    def __init__(self, orders):
        self.orders = sorted(orders, key=lambda x: x.release_time)

    def get_orders(self, current_time):
        return [
            order
            for order in self.orders
            if order.release_time == current_time
        ]
