from src.dynamic.rolling_horizon import RollingHorizonDispatcher


class MockSolver:
    def solve(self, orders):
        return orders


def test_rolling_horizon_order_state():
    dispatcher = RollingHorizonDispatcher(MockSolver())

    dispatcher.add_orders([1, 2, 3])
    assert len(dispatcher.state.active_orders) == 3

    dispatcher.dispatch([1])
    assert 1 in dispatcher.state.executed_orders
    assert 1 not in dispatcher.state.active_orders
