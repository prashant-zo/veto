"""Command line entry point."""

import argparse
import sys

from . import config
from .collect.github import GitHub, GitHubError
from .collect.kube import Kube, KubeError, tag_of
from .collect.loki import Loki, LokiError
from .collect.prometheus import Prometheus, PromError
from .collect.query import BadInput, check_hash, check_name, quote, selector


def probe(args) -> int:
    s = config.load()
    ns, svc = check_name(args.namespace), check_name(args.service)
    kube = Kube(s.kube_context)
    hashes = kube.rollout_hashes(ns, svc)
    sides = {"stable": check_hash(hashes.stable)}
    if hashes.canary:
        sides["canary"] = check_hash(hashes.canary)

    print(f"rollout {ns}/{svc}")
    images = {}
    for side, h in sides.items():
        images[side] = kube.image_for_hash(ns, h, svc)
        print(f"  {side}: hash {h}, image {images[side]}")

    if "canary" not in sides:
        print("  no canary running")
    else:
        tag = tag_of(images["canary"])
        try:
            intent = GitHub(s.github_repo, s.github_token, s.http_timeout).intent_for_tag(tag)
        except GitHubError as e:
            print(f"  intent: error {e}")
        else:
            if intent is None:
                print(f"  intent: none, tag {tag!r} has no pr number")
            else:
                print(f"  intent: pr #{intent.number} {intent.title!r}, sha is head: {intent.sha_matches}, "
                      f"files: {len(intent.files)}, commits: {len(intent.commits)}")

    prom = Prometheus(s.prom_url, s.http_timeout)
    loki = Loki(s.loki_url, s.http_timeout)
    for side, h in sides.items():
        q = ("sum(rate(traces_span_metrics_calls_total"
             + selector(service_name=svc, span_kind="SPAN_KIND_SERVER", rollouts_pod_template_hash=h)
             + "[2m]))")
        try:
            res = prom.query(q)
            print(f"  {side}: {res[0].value if res else 0.0:.2f} req/s")
        except PromError as e:
            print(f"  {side}: prometheus error {e}")
        logql = selector(service_name=svc) + f" | rollouts_pod_template_hash={quote(h)}"
        try:
            lines = loki.lines(logql, since_s=120, limit=1000)
            print(f"  {side}: {len(lines)} log lines in 2m")
            for line in lines[-2:]:
                print(f"    {line.line}")
        except LokiError as e:
            print(f"  {side}: loki error {e}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="veto")
    sub = p.add_subparsers(dest="cmd", required=True)
    pr = sub.add_parser("probe", help="check that every source answers for a rollout")
    pr.add_argument("--namespace", default="shop")
    pr.add_argument("--service", required=True)
    pr.set_defaults(func=probe)
    args = p.parse_args(argv)
    try:
        return args.func(args)
    except (BadInput, KubeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
