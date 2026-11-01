import pytest

from veto.collect.query import BadInput, check_hash, check_name, quote, selector


def test_selector_quotes_values():
    assert selector(service_name="checkout", span_kind="SPAN_KIND_SERVER") == \
        '{service_name="checkout",span_kind="SPAN_KIND_SERVER"}'


def test_quote_escapes():
    assert quote('a"b\\c') == '"a\\"b\\\\c"'


@pytest.mark.parametrize("bad", ["", "Checkout", 'a"}', "x" * 64, "a b"])
def test_check_name_rejects(bad):
    with pytest.raises(BadInput):
        check_name(bad)


@pytest.mark.parametrize("bad", ["", 'abc"}', "5474FBCD59", "a" * 17, "../x"])
def test_check_hash_rejects(bad):
    with pytest.raises(BadInput):
        check_hash(bad)


def test_check_hash_accepts():
    assert check_hash("5474fbcd59") == "5474fbcd59"
