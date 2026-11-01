"""Safe building of PromQL and LogQL label matchers."""

import re

_NAME = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
_HASH = re.compile(r"^[a-z0-9]{1,16}$")


class BadInput(ValueError):
    pass


def check_name(value: str) -> str:
    if not _NAME.match(value or ""):
        raise BadInput(f"bad name: {value!r}")
    return value


def check_hash(value: str) -> str:
    if not _HASH.match(value or ""):
        raise BadInput(f"bad pod hash: {value!r}")
    return value


def quote(value: str) -> str:
    """Quote a label value for PromQL or LogQL."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def selector(**labels: str) -> str:
    """{a="x",b="y"} from keyword args. Keys come from our code, values get quoted."""
    inner = ",".join(f"{k}={quote(v)}" for k, v in labels.items())
    return "{" + inner + "}"


_WINDOW = re.compile(r"^[1-9][0-9]{0,2}[smh]$")


def check_window(value: str) -> str:
    if not _WINDOW.match(value or ""):
        raise BadInput(f"bad window: {value!r}")
    return value
