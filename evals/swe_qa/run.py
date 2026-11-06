#!/usr/bin/env python3
"""SWE-QA comprehension eval: blind the answers, then score them.

The protocol is in evals/README.md. Answers and judgments are produced by model calls outside
this script; this script only prepares inputs, hides which condition produced which answer,
and aggregates the official SWE-QA rubric scores (five dimensions, 1-20 each, 100 total).

usage:
  run.py questions <data.jsonl> <run_dir>             number the questions (q01, q02, ...)
  run.py blind <run_dir> [--batches N] [--seed S]      shuffle all answers into judge batches
  run.py score <run_dir>                               unblind and aggregate into results.json/.md
"""
import argparse
import glob
import hashlib
import json
import os
import random
import statistics
import sys

DIMS = ["correctness", "completeness", "relevance", "clarity", "reasoning"]


def read_jsonl(path):
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def write_jsonl(path, rows):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")


def cmd_questions(args):
    rows = read_jsonl(args.data)
    out = [{"id": "q%02d" % (i + 1), "question": r["question"], "reference": r["answer"]} for i, r in enumerate(rows)]
    write_jsonl(os.path.join(args.run_dir, "questions.jsonl"), out)
    with open(os.path.join(args.run_dir, "questions.md"), "w", encoding="utf-8") as fh:
        for r in out:
            fh.write("%s: %s\n\n" % (r["id"], r["question"]))
    print("%d questions -> %s" % (len(out), args.run_dir))


def cmd_blind(args):
    qs = {q["id"]: q for q in read_jsonl(os.path.join(args.run_dir, "questions.jsonl"))}
    items = []
    for path in sorted(glob.glob(os.path.join(args.run_dir, "answers", "*.jsonl"))):
        cond = os.path.splitext(os.path.basename(path))[0]
        answers = {a["id"]: a["answer"] for a in read_jsonl(path)}
        missing = sorted(set(qs) - set(answers))
        if missing:
            sys.exit("%s is missing answers for %s" % (cond, ", ".join(missing)))
        for qid, ans in answers.items():
            key = hashlib.sha1(("%s|%s|%s" % (args.seed, cond, qid)).encode()).hexdigest()[:10]
            items.append({"key": key, "cond": cond, "id": qid, "answer": ans})
    random.Random(args.seed).shuffle(items)
    jdir = os.path.join(args.run_dir, "judge")
    os.makedirs(jdir, exist_ok=True)
    with open(os.path.join(jdir, "key.json"), "w", encoding="utf-8") as fh:
        json.dump({it["key"]: [it["cond"], it["id"]] for it in items}, fh, indent=1)
    size = -(-len(items) // args.batches)
    for b in range(args.batches):
        chunk = items[b * size:(b + 1) * size]
        write_jsonl(os.path.join(jdir, "batch-%d.jsonl" % (b + 1)), [
            {"key": it["key"], "question": qs[it["id"]]["question"], "reference": qs[it["id"]]["reference"],
             "candidate": it["answer"]} for it in chunk])
    print("%d answers from %d conditions -> %d blind batches in %s" % (
        len(items), len({i["cond"] for i in items}), args.batches, jdir))


def bootstrap_ci(values, seed=0, n=4000):
    rng = random.Random(seed)
    means = sorted(statistics.fmean(rng.choices(values, k=len(values))) for _ in range(n))
    return means[int(0.025 * n)], means[int(0.975 * n) - 1]


def cmd_score(args):
    jdir = os.path.join(args.run_dir, "judge")
    with open(os.path.join(jdir, "key.json"), encoding="utf-8") as fh:
        key = json.load(fh)
    scores = {}
    for path in sorted(glob.glob(os.path.join(jdir, "judged-*.jsonl"))):
        for j in read_jsonl(path):
            if j["key"] not in key:
                continue
            if not all(isinstance(j.get(d), int) and 1 <= j[d] <= 20 for d in DIMS):
                sys.exit("invalid judgment for %s in %s" % (j["key"], path))
            cond, qid = key[j["key"]]
            scores.setdefault(cond, {})[qid] = {d: j[d] for d in DIMS}
    missing = [k for k, (c, q) in key.items() if q not in scores.get(c, {})]
    if missing:
        sys.exit("%d answers have no judgment yet" % len(missing))
    results = {"conditions": {}, "head_to_head": {}}
    for cond, per_q in scores.items():
        totals = [sum(v.values()) for v in per_q.values()]
        lo, hi = bootstrap_ci(totals)
        results["conditions"][cond] = {
            "n": len(totals), "mean_total": round(statistics.fmean(totals), 2), "ci95": [round(lo, 2), round(hi, 2)],
            "dims": {d: round(statistics.fmean(v[d] for v in per_q.values()), 2) for d in DIMS}}
    if "onramp" in scores:
        for cond in scores:
            if cond == "onramp":
                continue
            w = t = l = 0
            for qid, v in scores["onramp"].items():
                a, b = sum(v.values()), sum(scores[cond][qid].values())
                w, t, l = w + (a > b), t + (a == b), l + (a < b)
            results["head_to_head"]["onramp_vs_" + cond] = {"wins": w, "ties": t, "losses": l}
    with open(os.path.join(args.run_dir, "results.json"), "w", encoding="utf-8") as fh:
        json.dump(results, fh, indent=1)
    order = sorted(results["conditions"], key=lambda c: -results["conditions"][c]["mean_total"])
    lines = ["| Condition | Score /100 | 95% CI | " + " | ".join(d.capitalize() for d in DIMS) + " |",
             "|---|---|---|" + "---|" * len(DIMS)]
    for c in order:
        r = results["conditions"][c]
        lines.append("| %s | **%.1f** | %.1f to %.1f | %s |" % (c, r["mean_total"], r["ci95"][0], r["ci95"][1],
                                                         " | ".join("%.1f" % r["dims"][d] for d in DIMS)))
    for k, v in results["head_to_head"].items():
        lines.append("\n%s: %d wins, %d ties, %d losses" % (k.replace("_", " "), v["wins"], v["ties"], v["losses"]))
    with open(os.path.join(args.run_dir, "results.md"), "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    print("\n".join(lines))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    q = sub.add_parser("questions")
    q.add_argument("data")
    q.add_argument("run_dir")
    b = sub.add_parser("blind")
    b.add_argument("run_dir")
    b.add_argument("--batches", type=int, default=4)
    b.add_argument("--seed", type=int, default=11)
    s = sub.add_parser("score")
    s.add_argument("run_dir")
    args = ap.parse_args(argv)
    {"questions": cmd_questions, "blind": cmd_blind, "score": cmd_score}[args.cmd](args)


if __name__ == "__main__":
    main()
