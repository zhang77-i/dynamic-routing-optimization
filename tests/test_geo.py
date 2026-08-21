import numpy as np

from lade_routing.geo import haversine_meters, lonlat_to_web_mercator


def test_web_mercator_origin() -> None:
    x, y = lonlat_to_web_mercator(np.array([0.0]), np.array([0.0]))
    assert np.isclose(x[0], 0.0)
    assert np.isclose(y[0], 0.0)


def test_haversine_zero_distance() -> None:
    distance = haversine_meters(126.5, 43.8, 126.5, 43.8)
    assert np.isclose(float(distance), 0.0)
