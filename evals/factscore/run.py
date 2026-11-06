#!/usr/bin/env python3
"""FActScore-style grounding eval: sample atomic claims blind, then score support.

FActScore (Min et al., EMNLP 2023) splits a long generation into atomic facts and reports the
share that a knowledge source supports. Here the knowledge source is the repository itself at a
pinned commit. Claim extraction and judging are model calls outside this script; this script
samples claims reproducibly, hides which document each came from, and aggregates the verdicts.

usage:
  run.py sample <run_dir> [--n 50] [--seed S]     claims-<doc>.jsonl -> blind judge batch + key
  run.py score <run_dir>                          judged.jsonl + key -> results.json/.md
"""
import argparse
import glob
import hashlib
import json
import os
import random
import sys

VERDICTS = ("supported", "unsupported")


def read_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def cmd_sample(args):
    rng = random.Random(args.seed)
    items = []
    for path in sorted(glob.glob(os.path.join(args.run_dir, "claims-*.jsonl"))):
        doc = os.path.basename(path)[len("claims-"):-len(".jsonl")]
        claims = [c for c in read_jsonl(path) if c.get("claim", "").strip()]
        picked = rng.sample(claims, min(args.n, len(claims)))
        for c in picked:
            key = hashlib.sha1(("%s|%s|%s" % (args.seed, doc, c["claim"])).encode()).hexdigest()[:10]
            items.append({"key": key, "doc": doc, "claim": c["claim"], "extracted": len(claims)})
    rng.shuffle(items)
    with open(os.path.join(args.run_dir, "key.json"), "w", encoding="utf-8") as fh:
        json.dump({i["key"]: i["doc"] for i in items}, fh, indent=1)
    with open(os.path.join(args.run_dir, "judge-batch.jsonl"), "w", encoding="utf-8") as fh:
        for i in items:
            fh.write(json.dumps({"key": i["key"], "claim": i["claim"]}, ensure_ascii=False) + "\n")
    counts = {}
    for i in items:
        counts[i["doc"]] = (counts.get(i["doc"], 0) + 1, i["extracted"])
    print("blind batch of %d claims: %s" % (len(items), ", ".join("%s %d of %d" % (d, n, t) for d, (n, t) in counts.items())))


def cmd_score(args):
    with open(os.path.join(args.run_dir, "key.json"), encoding="utf-8") as fh:
        key = json.load(fh)
    verdicts = {}
    for path in sorted(glob.glob(os.path.join(args.run_dir, "judged*.jsonl"))):
        for j in read_jsonl(path):
            if j.get("key") in key:
                if j.get("verdict") not in VERDICTS:
                    sys.exit("bad verdict for %s: %r" % (j.get("key"), j.get("verdict")))
                verdicts[j["key"]] = j["verdict"]
    missing = set(key) - set(verdicts)
    if missing:
        sys.exit("%d claims have no verdict yet" % len(missing))
    per_doc = {}
    for k, doc in key.items():
        s, n = per_doc.get(doc, (0, 0))
        per_doc[doc] = (s + (verdicts[k] == "supported"), n + 1)
    results = {doc: {"supported": s, "judged": n, "factscore": round(100.0 * s / n, 1)} for doc, (s, n) in per_doc.items()}
    with open(os.path.join(args.run_dir, "results.json"), "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=1)
    lines = ["| Document | Claims judged | Supported by the code | FActScore |", "|---|---|---|---|"]
    for doc in sorted(results, key=lambda d: -results[d]["factscore"]):
        r = results[doc]
        lines.append("| %s | %d | %d | **%.1f%%** |" % (doc, r["judged"], r["supported"], r["factscore"]))
    with open(os.path.join(args.run_dir, "results.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("run_dir")
    s.add_argument("--n", type=int, default=50)
    s.add_argument("--seed", type=int, default=5)
    c = sub.add_parser("score")
    c.add_argument("run_dir")
    args = ap.parse_args(argv)
    {"sample": cmd_sample, "score": cmd_score}[args.cmd](args)


if __name__ == "__main__":
    main()
