import pytest

from veto.collect.query import BadInput, check_window


def test_check_window():
    assert check_window("2m") == "2m"
    for bad in ["", "0m", "2", "2d", "2m]", "1000s"]:
        with pytest.raises(BadInput):
            check_window(bad)
