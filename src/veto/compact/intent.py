"""What the PR says it does, cleaned for the judge, plus hard evidence when it cannot be trusted.

PR text is written by whoever opened the PR, so it is untrusted like logs:
cleaned, redacted, cut to size and scanned for text aimed at the reviewer.
"""

from collections import Counter

from ..collect.github import Intent
from .injection import attack_signs
from .model import Evidence
from .redact import clean, redact

MAX_TITLE = 300
MAX_BODY = 4000
MAX_COMMITS = 20
MAX_COMMIT = 500
MAX_FILES = 20
MAX_PATCH = 4000
MAX_ATTACKS = 5


def _text(s: str, limit: int, redacted: Counter) -> str:
    out, counts = redact(clean(s or "", None))
    redacted.update(counts)
    return out if len(out) <= limit else out[:limit] + "\n[cut]"


def added_lines(patch: str | None) -> list[str]:
    return [ln[1:] for ln in (patch or "").splitlines() if ln.startswith("+") and not ln.startswith("+++")]


def intent_doc(intent: Intent, redacted: Counter) -> dict:
    files = [{"path": f.path, "status": f.status, "patch": _text(f.patch or "", MAX_PATCH, redacted)}
             for f in intent.files[:MAX_FILES]]
    return {
        "pr": intent.number,
        "title": _text(intent.title, MAX_TITLE, redacted),
        "body": _text(intent.body, MAX_BODY, redacted),
        "commits": [_text(c, MAX_COMMIT, redacted) for c in intent.commits[:MAX_COMMITS]],
        "head_sha": intent.head_sha,
        "sha_matches": intent.sha_matches,
        "files": files,
        "files_not_shown": max(0, len(intent.files) - MAX_FILES),
    }


def intent_evidence(tag: str, intent: Intent | None, error: str | None) -> list[Evidence]:
    if error:
        return [Evidence("intent_unavailable", True, f"could not read the pull request for {tag!r}: {error}",
                         detail={"tag": tag})]
    if intent is None:
        return [Evidence("intent_missing", True,
                         f"image tag {tag!r} does not point to a pull request, so there is no stated intent to check",
                         detail={"tag": tag})]
    found = []
    if not intent.sha_matches:
        found.append(Evidence("intent_sha_mismatch", True,
                              f"image {tag!r} was not built from the head of PR #{intent.number} "
                              f"({intent.head_sha[:7]})", detail={"tag": tag, "head_sha": intent.head_sha}))

    places = [("title", intent.title), ("body", intent.body)]
    places += [(f"commit {i + 1}", c) for i, c in enumerate(intent.commits)]
    places += [(f"added lines in {f.path}", "\n".join(added_lines(f.patch))) for f in intent.files]
    attacks = 0
    for where, text in places:
        signs = attack_signs(clean(text or "", None))   # scan all of it, not only what is shown
        if signs and attacks < MAX_ATTACKS:
            attacks += 1
            found.append(Evidence("pr_injection", True,
                                  f"PR #{intent.number} {where} has text aimed at the reviewer ({', '.join(signs)})",
                                  detail={"where": where, "signs": signs}))
    return found
