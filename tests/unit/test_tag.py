from veto.collect.kube import tag_of


def test_tag_of():
    assert tag_of("veto-shop:pr-2-ac3b97a") == "pr-2-ac3b97a"
    assert tag_of("localhost:5000/veto-shop:main-a13119d") == "main-a13119d"
    assert tag_of("ghcr.io/x/veto@sha256:abc") == ""
    assert tag_of("veto-shop") == ""
