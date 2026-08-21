from lade_routing.road_graph import parse_linestring


def test_linestring_parser() -> None:
    line = parse_linestring("LINESTRING (0 0, 3 4, 6 4)")
    assert line is not None
    assert line.start_x == 0
    assert line.end_x == 6
    assert line.length_m == 8


def test_linestring_parser_rejects_other_geometry() -> None:
    assert parse_linestring("MULTILINESTRING ((0 0, 1 1))") is None
