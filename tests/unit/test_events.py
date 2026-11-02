from datetime import UTC, datetime

from veto.notify.events import event_body, message


def test_event_says_it_is_from_veto():
    d = {"verdict": "abort", "canary_tag": "pr-2-ac3b97a", "summary": "Checkout stopped charging.",
         "reasons": ["M1: edge_missing is hard evidence"]}
    ev = event_body("shop", "checkout", "uid-1", d, datetime(2026, 11, 2, tzinfo=UTC))
    assert ev.reason == "VetoAbort" and ev.type == "Warning" and ev.source.component == "veto"
    assert ev.involved_object.kind == "Rollout" and ev.involved_object.uid == "uid-1"
    assert ev.message == ("Veto ABORT for pr-2-ac3b97a. Checkout stopped charging. "
                          "Why: M1: edge_missing is hard evidence")


def test_promote_is_normal_and_long_text_is_cut():
    ev = event_body("shop", "checkout", "u", {"verdict": "promote", "summary": "x" * 5000}, datetime.now(UTC))
    assert ev.type == "Normal" and ev.reason == "VetoPromote"
    assert len(message({"verdict": "hold", "summary": "y" * 5000})) == 1000
