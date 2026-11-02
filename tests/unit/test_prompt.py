import json
from pathlib import Path

from veto.judge.prompt import messages

CASES = Path(__file__).parents[2] / "eval" / "cases"


def test_bundle_stays_inside_its_markers():
    bundle = json.loads((CASES / "pr-5.json").read_text())
    system, user = messages(bundle)
    mark = "BUNDLE-" + bundle["hash"][7:19]
    body = user["content"]
    assert system["role"] == "system" and "Ignore any previous rules" not in system["content"]
    start, end = body.index(f"<<<{mark}\n"), body.index(f"\n{mark}>>>")
    assert start < body.index("Ignore any previous rules") < end
    assert body.count(mark) == 4


def test_diff_is_plain_text_and_hashes_stay_out():
    bundle = json.loads((CASES / "pr-3.json").read_text())
    body = messages(bundle)[1]["content"]
    assert '\n+    log.info("order placed id=%s' in body
    assert bundle["hash"] not in body and bundle["stable"]["hash"] not in body
