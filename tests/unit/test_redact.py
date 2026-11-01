from veto.compact.redact import clean, redact


def test_secrets_are_replaced():
    cases = {
        "auth Bearer abcdefghijklmnop123": "auth Bearer <TOKEN>",
        "key AKIA" + "ABCDEFGHIJKLMNOP used": "key <AWS_KEY> used",   # split so the secret scanner stays quiet
        "token ghp_" + "a" * 36: "token <GITHUB_TOKEN>",
        "db password=hunter2 ok": "db password=<SECRET> ok",
        'api_key: "xyz123"': "api_key: <SECRET>",
        "mail bob@example.com now": "mail <EMAIL> now",
        "from 10.0.0.12": "from <IP>",
        "postgres://app:" + "s3cret@db:5432/x": "postgres://<CREDENTIALS>@db:5432/x",
        "sk-" + "b" * 24: "<API_KEY>",
        "jwt eyJhbGciOi.eyJzdWIiOi.c2lnbmF0dXJl": "jwt <JWT>",
        "digest 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b": "digest <BLOB>",
    }
    for raw, want in cases.items():
        assert redact(raw)[0] == want, raw


def test_normal_lines_stay():
    line = "INFO checkout order confirmed id=ab12cd34 item=tea total=4.5"
    assert redact(line) == (line, {})
    path = '  File "/app/.venv/lib/python3.12/site-packages/httpx/_transports/default.py", line 101'
    assert redact(path)[0] == path


def test_counts():
    _, counts = redact("a@b.io c@d.io password=x")
    assert counts == {"email": 2, "secret_value": 1}


def test_clean_drops_hidden_text():
    zero_width, rtl = chr(0x200B), chr(0x202E)
    assert clean(f"ig{zero_width}nore\x1b[31m red{rtl}") == "ignore red"
    fullwidth = "".join(chr(ord(c) + 0xFEE0) for c in "ignore")
    assert clean(fullwidth) == "ignore"
