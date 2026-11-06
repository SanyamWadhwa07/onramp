#!/usr/bin/env python3
"""Fault-injection eval for verify.py (mutation testing).

Takes guides that already pass verification and plants known faults in copies of them, one
citation at a time, then runs the verifier and records what it does:

  fabricated  the anchor is changed into text that appears nowhere in the file
              -> must be rejected
  missing     the path is changed to a file that does not exist
              -> must be rejected
  drift       the line range is shifted while the anchor stays real
              -> must be re-anchored to the original lines
  control     the citation is left untouched
              -> must pass (a failure here is a false alarm)

usage: python evals/fault_injection.py <repo> [<repo> ...] [--per-kind N] [--seed S] [--out FILE]
Each <repo> must contain a verified .onramp/guide.json.
"""
import argparse
import copy
import json
import os
import random
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "skills", "onramp", "scripts"))
from _common import CITE_RE, norm_ws, read_lines  # noqa: E402
import verify  # noqa: E402


def citations(guide):
    """Yield (container, key, match) for every line citation, so it can be rewritten in place."""
    def walk(node):
        if isinstance(node, dict):
            items = list(node.items())
        elif isinstance(node, list):
            items = list(enumerate(node))
        else:
            return
        for k, v in items:
            if isinstance(v, str):
                for m in CITE_RE.finditer(v):
                    if m.group(2) and m.group(4):
                        yield node, k, m
            else:
                yield from walk(v)
    yield from walk({k: v for k, v in guide.items() if k != "verification"})


def fabricate(anchor, file_text, rng):
    """Turn a real anchor into a plausible one that is not in the file."""
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", anchor)
    suffixes = ["_v2", "_async", "_legacy", "_cache", "_internal"]
    for _ in range(10):
        if words:
            w = rng.choice(words)
            fake = anchor.replace(w, w + rng.choice(suffixes), 1)
        else:
            fake = anchor + rng.choice(suffixes)
        if norm_ws(fake) not in norm_ws(file_text):
            return fake
    return None


def run_one(root, guide, container, key, old, new):
    """Write the mutated guide to a scratch file, verify it with --fix, return (errors, fixed text)."""
    g = copy.deepcopy(guide)
    path_to_value = []

    def locate(node, target, trail):
        if node is target:
            return trail
        if isinstance(node, dict):
            for k, v in node.items():
                r = locate(v, target, trail + [k])
                if r is not None:
                    return r
        elif isinstance(node, list):
            for i, v in enumerate(node):
                r = locate(v, target, trail + [i])
                if r is not None:
                    return r
        return None

    trail = locate(guide, container, [])
    node = g
    for step in trail:
        node = node[step]
    node[key] = node[key].replace(old, new, 1)
    path_to_value.append((trail, key))
    scratch = os.path.join(root, ".onramp", "fault-injection.json")
    with open(scratch, "w", encoding="utf-8") as fh:
        json.dump(g, fh)
    rep, _ = verify.verify(root, scratch, fix=True)
    with open(scratch, encoding="utf-8") as fh:
        fixed = json.load(fh)
    os.remove(scratch)
    node = fixed
    for step in trail:
        node = node[step]
    return rep.errors, node[key]


def evaluate(root, per_kind, rng):
    with open(os.path.join(root, ".onramp", "guide.json"), encoding="utf-8") as fh:
        guide = json.load(fh)
    cites = list(citations(guide))
    rng.shuffle(cites)
    sample = cites[:per_kind]
    out = {"repo": os.path.basename(os.path.abspath(root)), "citations_in_guide": len(cites), "cases": []}
    for container, key, m in sample:
        path, s, e, anchor = m.group(1).strip(), int(m.group(2)), int(m.group(3) or m.group(2)), m.group(4)
        original = m.group(0)
        lines = read_lines(os.path.join(root, path)) or []
        text = "\n".join(lines)
        cases = [("control", original)]
        fake = fabricate(anchor, text, rng)
        if fake:
            cases.append(("fabricated", "[[%s:%d-%d|%s]]" % (path, s, e, fake)))
        stem, ext = os.path.splitext(path)
        cases.append(("missing", "[[%s_old%s:%d-%d|%s]]" % (stem, ext, s, e, anchor)))
        shift = rng.choice([-9, -5, -3, 3, 5, 9])
        ns, ne = s + shift, e + shift
        if ns >= 1 and ne <= len(lines) and not verify.find_anchor(lines, anchor, ns, ne):
            cases.append(("drift", "[[%s:%d-%d|%s]]" % (path, ns, ne, anchor)))
        for kind, mutated in cases:
            errors, after = run_one(root, guide, container, key, original, mutated)
            if kind == "control":
                ok = not errors
            elif kind in ("fabricated", "missing"):
                ok = bool(errors)
            else:
                expected = verify.nearest_anchor(lines, anchor, ns)
                ok = not errors and ("[[%s:%d" % (path, expected)) in after
            out["cases"].append({"kind": kind, "ok": ok, "citation": original[:160], "mutant": mutated[:160]})
    return out


def summarize(results):
    table = {}
    for r in results:
        for c in r["cases"]:
            t = table.setdefault(c["kind"], [0, 0])
            t[0] += c["ok"]
            t[1] += 1
    return table


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("repos", nargs="+")
    ap.add_argument("--per-kind", type=int, default=60, help="citations sampled per repo")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    rng = random.Random(args.seed)
    results = [evaluate(os.path.abspath(r), args.per_kind, rng) for r in args.repos]
    table = summarize(results)
    labels = {"fabricated": "fabricated anchors rejected", "missing": "missing files rejected",
              "drift": "drifted lines re-anchored correctly", "control": "real citations accepted"}
    print("FAULT INJECTION  seed %d, %s" % (args.seed, ", ".join("%s (%d citations)" % (r["repo"], r["citations_in_guide"]) for r in results)))
    for kind in ("fabricated", "missing", "drift", "control"):
        if kind in table:
            ok, n = table[kind]
            print("  %-38s %4d / %-4d  %5.1f%%" % (labels[kind], ok, n, 100.0 * ok / n))
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump({"seed": args.seed, "summary": {k: {"passed": v[0], "total": v[1]} for k, v in table.items()},
                       "repos": results}, fh, indent=1)
    failed = sum(n - ok for ok, n in table.values())
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
