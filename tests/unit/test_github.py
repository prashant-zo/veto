import httpx
import pytest

from veto.collect.github import GitHub, GitHubError, parse_tag


def handler(request):
    path = request.url.path
    if path == "/repos/o/r/pulls/2":
        return httpx.Response(200, json={"title": "refactor pricing helpers", "body": "No behavior change.",
                                         "head": {"sha": "ac3b97a0000000000000000000000000000000ab"}})
    if path == "/repos/o/r/pulls/2/commits":
        return httpx.Response(200, json=[{"sha": "ac3b97a", "commit": {"message": "refactor pricing helpers"}}])
    if path == "/repos/o/r/pulls/2/files":
        return httpx.Response(200, json=[{"filename": "shop/checkout.py", "status": "modified", "patch": "@@\n-a\n+b"}])
    return httpx.Response(404, json={"message": "Not Found"})


def gh():
    return GitHub("o/r", transport=httpx.MockTransport(handler))


def test_parse_tag():
    assert parse_tag("pr-2-ac3b97a") == (2, "ac3b97a")
    assert parse_tag("main-a13119d") is None
    assert parse_tag("pr-x-ac3b97a") is None
    assert parse_tag("") is None


def test_intent_for_matching_tag():
    intent = gh().intent_for_tag("pr-2-ac3b97a")
    assert intent.number == 2
    assert intent.title == "refactor pricing helpers"
    assert intent.sha_matches is True
    assert intent.files[0].path == "shop/checkout.py"
    assert intent.commits == ["refactor pricing helpers"]


def test_sha_that_is_not_head_does_not_match():
    assert gh().intent_for_tag("pr-2-deadbee").sha_matches is False


def test_tag_without_pr_has_no_intent():
    assert gh().intent_for_tag("main-a13119d") is None


def test_missing_pr_is_no_intent():
    assert gh().intent_for_tag("pr-9-ac3b97a") is None


def test_github_down_raises():
    down = GitHub("o/r", transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    with pytest.raises(GitHubError):
        down.intent_for_tag("pr-2-ac3b97a")
