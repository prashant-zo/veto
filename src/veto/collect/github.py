"""Read-only GitHub client: find the PR behind an image tag."""

import re
from dataclasses import dataclass

import httpx

TAG_RE = re.compile(r"^pr-(\d+)-([0-9a-f]{7,40})$")


class GitHubError(RuntimeError):
    pass


@dataclass(frozen=True)
class ChangedFile:
    path: str
    status: str
    patch: str | None


@dataclass(frozen=True)
class Intent:
    number: int
    title: str
    body: str
    commits: list[str]
    files: list[ChangedFile]
    head_sha: str
    sha_matches: bool


def parse_tag(tag: str) -> tuple[int, str] | None:
    m = TAG_RE.match(tag or "")
    if not m:
        return None
    return int(m.group(1)), m.group(2)


class GitHub:
    def __init__(self, repo: str, token: str | None = None, timeout: float = 10.0,
                 transport: httpx.BaseTransport | None = None, base_url: str = "https://api.github.com"):
        headers = {"Accept": "application/vnd.github+json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        self._http = httpx.Client(base_url=base_url, headers=headers, timeout=timeout, transport=transport)
        self.repo = repo

    def _get(self, path: str, params: dict | None = None):
        try:
            r = self._http.get(path, params=params)
            r.raise_for_status()
            return r.json()
        except (httpx.HTTPError, ValueError) as e:
            raise GitHubError(f"{path}: {e}") from e

    def intent_for_tag(self, tag: str) -> Intent | None:
        """None when the tag carries no PR number. The sha in the tag must be the PR head."""
        parsed = parse_tag(tag)
        if parsed is None:
            return None
        number, sha = parsed
        base = f"/repos/{self.repo}/pulls/{number}"
        pr = self._get(base)
        commits = self._get(f"{base}/commits", {"per_page": 100})
        files = self._get(f"{base}/files", {"per_page": 100})
        head_sha = pr["head"]["sha"]
        return Intent(
            number=number,
            title=pr.get("title") or "",
            body=pr.get("body") or "",
            commits=[c["commit"]["message"] for c in commits],
            files=[ChangedFile(f["filename"], f["status"], f.get("patch")) for f in files],
            head_sha=head_sha,
            sha_matches=head_sha.startswith(sha),
        )
