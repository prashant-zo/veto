import pytest

from veto.judge.parse import BadAnswer, parse_answer

IDS = {"M1", "L1"}
GOOD = '{"verdict": "Abort", "findings": [{"id": "M1", "explained_by_pr": false, "why": "lost call"}], "summary": "s"}'


def test_good_answer():
    a = parse_answer(GOOD, IDS)
    assert a.verdict == "abort" and a.explained() == {"M1": False} and a.summary == "s"


def test_wrapped_answers_still_parse():
    assert parse_answer("<think>hmm</think>" + GOOD, IDS).verdict == "abort"
    assert parse_answer("```json\n" + GOOD + "\n```", IDS).verdict == "abort"


@pytest.mark.parametrize("text", [
    None, "", "no json here", "[1, 2]",
    '{"verdict": "ship it", "findings": []}',
    '{"verdict": "hold"}',
    '{"verdict": "hold", "findings": [{"id": "X9", "explained_by_pr": true}]}',
    '{"verdict": "hold", "findings": [{"id": "M1", "explained_by_pr": "yes"}]}',
    '{"verdict": "hold", "findings": [{"id": "M1", "explained_by_pr": true}, {"id": "M1", "explained_by_pr": true}]}',
])
def test_bad_answers_are_refused(text):
    with pytest.raises(BadAnswer):
        parse_answer(text, IDS)
