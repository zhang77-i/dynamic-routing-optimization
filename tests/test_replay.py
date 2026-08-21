import pandas as pd

from lade_routing.replay import build_replay_batches


def test_replay_batches_are_time_ordered() -> None:
    batches = build_replay_batches(
        pd.Series([601, 10, 599]),
        pd.Series([3, 1, 2]),
        interval_seconds=300,
    )
    assert [batch.decision_time for batch in batches] == [0, 300, 600]
    assert batches[0].released_order_ids == (1,)
