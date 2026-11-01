from veto.compact.metrics import compare, window_seconds
from veto.compact.model import EdgeStat, SideStats


def side(h, rps=2.0, err=0.0, p99=30.0, **edges):
    return SideStats(hash=h, rps=rps, err_ratio=err, p99_ms=p99,
                     edges={d: EdgeStat(v[0], v[1]) for d, v in edges.items()})


def kinds(found):
    return sorted(e.kind for e in found)


def test_same_behavior_gives_nothing():
    s = side("a", pricing=(2.0, 0.0), payments=(2.0, 0.0))
    c = side("b", pricing=(2.1, 0.0), payments=(1.9, 0.0))
    found, enough = compare("checkout", s, c, 120)
    assert found == [] and enough


def test_missing_edge_is_hard():
    s = side("a", pricing=(2.0, 0.0), payments=(2.0, 0.0))
    c = side("b", pricing=(2.0, 0.0))
    found, _ = compare("checkout", s, c, 120)
    assert kinds(found) == ["edge_missing"]
    assert found[0].hard and found[0].detail["destination"] == "payments"


def test_new_edge():
    s = side("a", pricing=(2.0, 0.0))
    c = side("b", pricing=(2.0, 0.0), queue=(2.0, 0.0))
    assert kinds(compare("checkout", s, c, 120)[0]) == ["edge_new"]


def test_errors_latency_and_edge_errors():
    s = side("a", p99=30.0, payments=(2.0, 0.0))
    c = side("b", err=1.0, p99=2000.0, payments=(2.0, 2.0))
    assert kinds(compare("checkout", s, c, 120)[0]) == ["edge_errors", "error_rate_up", "latency_up"]


def test_edge_shift():
    s = side("a", payments=(2.0, 0.0))
    c = side("b", payments=(4.0, 0.0))
    assert kinds(compare("checkout", s, c, 120)[0]) == ["edge_rate_shift"]


def test_low_traffic_is_flagged():
    assert compare("checkout", side("a", rps=0.1), side("b", rps=0.1), 120)[1] is False


def test_window_seconds():
    assert window_seconds("2m") == 120
    assert window_seconds("90s") == 90
    assert window_seconds("1h") == 3600


def test_tiny_sample_reports_nothing():
    found, enough = compare("checkout", side("a", rps=0.1), side("b", rps=0.1, err=1.0), 120)
    assert found == [] and not enough


def test_low_traffic_still_shows_hard_evidence():
    # like pr 4 live: the hanging canary slowed the load to 36 and 49 requests
    s = side("a", rps=0.3, payments=(0.3, 0.0))
    c = side("b", rps=0.41, err=1.0, payments=(0.41, 0.41))
    found, enough = compare("checkout", s, c, 120)
    assert kinds(found) == ["edge_errors", "error_rate_up"] and not enough
