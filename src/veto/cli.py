"""Command line entry point."""

import argparse
import json
import sys
from pathlib import Path

from . import config
from .bundle import collect as collect_bundle
from .collect.github import GitHub, GitHubError
from .collect.kube import Kube, KubeError, tag_of
from .collect.loki import Loki, LokiError
from .collect.prometheus import PromError, Prometheus
from .collect.query import BadInput, check_hash, check_name, quote, selector
from .compact.metrics import window_seconds
from .evidence import gather


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


def evidence(args) -> int:
    try:
        g = gather(config.load(), args.namespace, args.service, args.window)
    except PromError as e:
        print(f"prometheus error: {e}")
        return 3
    except LokiError as e:
        print(f"loki error: {e}")
        return 3
    if g is None:
        print("no canary running")
        return 1
    ws = window_seconds(g.window)
    for name, st in (("stable", g.stable), ("canary", g.canary)):
        edges = ", ".join(f"{d} {e.rps:.2f}/s" for d, e in sorted(st.edges.items())) or "none"
        p99 = f"{st.p99_ms:.0f}ms" if st.p99_ms is not None else "n/a"
        print(f"{name}: hash {st.hash}, {st.rps:.2f} req/s ({st.rps * ws:.0f} in {g.window}), "
              f"errors {st.err_ratio:.1%}, p99 {p99}, calls: {edges}")
    lg = g.logs
    redacted = ", ".join(f"{k} {v}" for k, v in sorted(lg.redacted.items())) or "nothing"
    print(f"logs: stable {lg.lines['stable']} lines + {lg.lines['stable_startup']} at startup, "
          f"canary {lg.lines['canary']} + {lg.lines['canary_startup']}, "
          f"{len(lg.canary_total)} canary templates, redacted: {redacted}")
    if lg.truncated:
        print("logs: hit the loki line limit, counts are partial")
    print(f"enough traffic to promote: {g.enough}")
    if not g.found:
        print("no anomalies")
    for e in g.found:
        print(f"  [{'hard' if e.hard else 'soft'}] {e.kind}: {e.summary}")
    return 0


def bundle_cmd(args) -> int:
    try:
        b = collect_bundle(args.namespace, args.service, args.window)
    except PromError as e:
        print(f"prometheus error: {e}")
        return 3
    except LokiError as e:
        print(f"loki error: {e}")
        return 3
    if b is None:
        print("no canary running")
        return 1
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(b, indent=2, ensure_ascii=True) + "\n")
    print(f"saved {out}, {b['hash'][:19]}, {len(b['evidence'])} evidence items")
    intent = b["intent"]
    if intent:
        print(f"intent: pr #{intent['pr']} {intent['title']!r}, sha is head: {intent['sha_matches']}, "
              f"files: {len(intent['files'])}")
    print(f"enough traffic to promote: {b['traffic']['enough_to_promote']}, redacted: {b['redacted'] or 'nothing'}")
    for e in b["evidence"]:
        print(f"  {e['id']} [{'hard' if e['hard'] else 'soft'}] {e['kind']}: {e['summary']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="veto")
    sub = p.add_subparsers(dest="cmd", required=True)

    pr = sub.add_parser("probe", help="check that every source answers for a rollout")
    pr.add_argument("--namespace", default="shop")
    pr.add_argument("--service", required=True)
    pr.set_defaults(func=probe)

    ev = sub.add_parser("evidence", help="canary vs stable evidence from metrics, edges and logs")
    ev.add_argument("--namespace", default="shop")
    ev.add_argument("--service", required=True)
    ev.add_argument("--window", default="2m")
    ev.set_defaults(func=evidence)

    bu = sub.add_parser("bundle", help="save the evidence bundle the judge will see")
    bu.add_argument("--namespace", default="shop")
    bu.add_argument("--service", required=True)
    bu.add_argument("--window", default="2m")
    bu.add_argument("--out", default=".local/bundle.json")
    bu.set_defaults(func=bundle_cmd)

    args = p.parse_args(argv)
    try:
        return args.func(args)
    except (BadInput, KubeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2
