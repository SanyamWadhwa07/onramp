#!/usr/bin/env python3
"""Check a guide against the code it describes.

Every [[path:start-end|anchor]] citation must point at a real file, real lines, and an anchor
that really appears inside those lines. Drifted line numbers are repaired with --fix when the
anchor is found elsewhere in the same file. An anchor that is nowhere in the file is an error:
the claim is unsupported and must be rewritten from the actual code.

usage: verify.py [repo] [--guide PATH] [--fix] [--merge]
exit status: 0 when there are no errors, 1 otherwise.
"""
import argparse
import datetime as dt
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import CITE_RE, load_json, norm_ws, onramp_dir, read_lines, run_git, save_json  # noqa: E402

CHAPTERS = ["gist", "run", "stack", "map", "concepts", "flows", "data", "files", "built", "why", "care", "practice"]
TIERS = {"core", "standard", "deep"}
GOALS = {"gist", "ship", "own", "rebuild"}
BACKGROUNDS = {"new", "know", "senior"}
VIEWS = {"quickstart", "stack", "architecture", "depmap", "concepts", "flow", "data", "files", "file",
         "milestones", "timeline", "decisions", "risks", "exercises", "languages"}
MERMAID_START = re.compile(
    r"^\s*(flowchart|graph|sequenceDiagram|classDiagram|erDiagram|stateDiagram(-v2)?|journey|gantt|"
    r"timeline|mindmap|gitGraph|pie|quadrantChart|block-beta|architecture-beta)\b")
SLUG = re.compile(r"^[a-z0-9][a-z0-9\-]*$")
MERGE_KEYS = ("lessons", "files", "flows", "concepts", "decisions", "risks", "stack", "milestones", "exercises")
MAX_RANGE = 120


class Report:
    def __init__(self):
        self.errors, self.warnings, self.fixed = [], [], []

    def err(self, where, msg):
        self.errors.append("%s: %s" % (where, msg))

    def warn(self, where, msg):
        self.warnings.append("%s: %s" % (where, msg))


class Files:
    def __init__(self, root):
        self.root = root
        self.cache = {}

    def exists(self, rel):
        return os.path.exists(os.path.join(self.root, rel))

    def lines(self, rel):
        if rel not in self.cache:
            self.cache[rel] = read_lines(os.path.join(self.root, rel))
        return self.cache[rel]


def safe_rel(path):
    p = path.strip().replace("\\", "/")
    if p.startswith("/") or re.match(r"^[A-Za-z]:", p) or ".." in p.split("/"):
        return None
    return p.lstrip("./") if p.startswith("./") else p


def find_anchor(lines, anchor, start, end):
    """Return the 1-based line where anchor begins inside [start, end], else None."""
    want = norm_ws(anchor)
    if not want:
        return None
    lo, hi = max(1, start), min(len(lines), end)
    window = [norm_ws(l) for l in lines[lo - 1:hi]]
    for i, l in enumerate(window):
        if want in l:
            return lo + i
    joined = " ".join(window)
    if want in joined:
        pos, acc = joined.index(want), 0
        for i, l in enumerate(window):
            acc += len(l) + 1
            if acc > pos:
                return lo + i
    return None


def nearest_anchor(lines, anchor, near):
    want = norm_ws(anchor)
    hits = [i + 1 for i, l in enumerate(lines) if want and want in norm_ws(l)]
    if not hits:
        for size in (2, 3, 4, 6):
            for i in range(len(lines) - size + 1):
                if want in norm_ws(" ".join(lines[i:i + size])):
                    hits.append(i + 1)
            if hits:
                break
    if not hits:
        return None
    return min(hits, key=lambda h: abs(h - near))


def check_citation(match, where, files, rep, stats):
    raw_path, s, e, anchor = match.group(1), match.group(2), match.group(3), match.group(4)
    rel = safe_rel(raw_path)
    stats["citations"] += 1
    if not rel:
        rep.err(where, "citation path must be repo-relative: [[%s]]" % raw_path)
        return None
    if not files.exists(rel):
        rep.err(where, "cited file does not exist: %s" % rel)
        return None
    stats["files"].add(rel)
    if s is None:
        stats["verified"] += 1
        return None
    start = int(s)
    end = int(e) if e else start
    lines = files.lines(rel)
    if lines is None:
        rep.err(where, "cannot read cited file as text: %s" % rel)
        return None
    if end < start:
        rep.err(where, "%s:%s-%s has end before start" % (rel, s, e))
        return None
    if end - start > MAX_RANGE:
        rep.warn(where, "%s:%d-%d spans %d lines; cite the specific part" % (rel, start, end, end - start + 1))
    if not anchor:
        rep.err(where, "%s:%d-%d needs an anchor: [[%s:%d-%d|exact text from those lines]]" % (rel, start, end, rel, start, end))
        return None
    if start > len(lines):
        found = nearest_anchor(lines, anchor, start)
        if found is None:
            rep.err(where, "%s has %d lines, cited %d-%d, and %r is not in the file" % (rel, len(lines), start, end, anchor))
            return None
    elif find_anchor(lines, anchor, start, end):
        stats["verified"] += 1
        want = norm_ws(anchor)
        if len(want) < 24 and sum(want in norm_ws(l) for l in lines) >= 4:
            rep.warn(where, "anchor %r appears on many lines of %s; quote text unique to %d-%d" % (anchor, rel, start, end))
        return None
    found = nearest_anchor(lines, anchor, start)
    if found is None:
        rep.err(where, "anchor %r is not in %s (unsupported claim; re-read the file and rewrite it)" % (anchor, rel))
        return None
    length = end - start
    new_start = found
    new_end = min(len(lines), found + length)
    fixed = "[[%s:%d%s|%s]]" % (rel, new_start, ("-%d" % new_end) if new_end != new_start else "", anchor)
    return fixed


def walk_strings(node, path, fn):
    """Apply fn(string, where) -> new string to every string in a JSON tree, in place."""
    if isinstance(node, dict):
        for k in list(node):
            v = node[k]
            if isinstance(v, str):
                node[k] = fn(v, "%s.%s" % (path, k))
            else:
                walk_strings(v, "%s.%s" % (path, k), fn)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            if isinstance(v, str):
                node[i] = fn(v, "%s[%d]" % (path, i))
            else:
                walk_strings(v, "%s[%d]" % (path, i), fn)


def check_mermaid(src, where, rep):
    if not isinstance(src, str) or not src.strip():
        return
    if not MERMAID_START.match(src):
        rep.err(where, "diagram must start with a mermaid type such as 'flowchart TD'")
    for m in re.finditer(r"\[([^\]\"\n]*[(){}][^\]\"\n]*)\]", src):
        rep.warn(where, 'quote mermaid labels that contain brackets: ["%s"]' % m.group(1))
        break


def need(obj, key, typ, where, rep, required=True):
    v = obj.get(key) if isinstance(obj, dict) else None
    if v is None:
        if required:
            rep.err(where, "missing '%s'" % key)
        return None
    if not isinstance(v, typ):
        rep.err(where, "'%s' should be %s" % (key, typ.__name__ if isinstance(typ, type) else "/".join(t.__name__ for t in typ)))
        return None
    return v


def check_structure(g, files, rep):
    proj = need(g, "project", dict, "guide", rep)
    if proj:
        need(proj, "name", str, "project", rep)
        need(proj, "one_liner", str, "project", rep)
    lessons = need(g, "lessons", list, "guide", rep) or []
    if not lessons:
        rep.err("guide", "no lessons")
    ids, flow_ids = set(), {f.get("id") for f in g.get("flows") or [] if isinstance(f, dict)}
    per_chapter, core_minutes = {c: 0 for c in CHAPTERS}, 0
    for i, l in enumerate(lessons):
        w = "lessons[%d]" % i
        if not isinstance(l, dict):
            rep.err(w, "lesson must be an object")
            continue
        lid = need(l, "id", str, w, rep)
        if lid:
            w = "lesson '%s'" % lid
            if not SLUG.match(lid):
                rep.err(w, "id must be a lowercase slug")
            if lid in ids:
                rep.err(w, "duplicate id")
            ids.add(lid)
        ch = need(l, "chapter", str, w, rep)
        if ch and ch not in CHAPTERS:
            rep.err(w, "chapter must be one of " + ", ".join(CHAPTERS))
        elif ch:
            per_chapter[ch] += 1
        need(l, "title", str, w, rep)
        need(l, "summary", str, w, rep)
        need(l, "body", str, w, rep)
        tier = need(l, "tier", str, w, rep)
        if tier and tier not in TIERS:
            rep.err(w, "tier must be core, standard or deep")
        mins = need(l, "minutes", int, w, rep)
        if mins is not None and not 1 <= mins <= 240:
            rep.err(w, "minutes must be between 1 and 240")
        if tier == "core" and mins:
            core_minutes += mins
        for key, allowed in (("goals", GOALS), ("for", BACKGROUNDS)):
            vals = need(l, key, list, w, rep, required=False) or []
            bad = [v for v in vals if v not in allowed]
            if bad:
                rep.err(w, "%s has unknown values %s (allowed: %s)" % (key, bad, ", ".join(sorted(allowed))))
        for j, s in enumerate(need(l, "show", list, w, rep, required=False) or []):
            if not isinstance(s, dict) or s.get("view") not in VIEWS:
                rep.err(w, "show[%d] must be {\"view\": one of %s}" % (j, ", ".join(sorted(VIEWS))))
                continue
            if s["view"] == "flow" and s.get("id") not in flow_ids:
                rep.err(w, "show[%d] refers to unknown flow '%s'" % (j, s.get("id")))
            if s["view"] == "file" and not files.exists(str(s.get("path", ""))):
                rep.err(w, "show[%d] refers to missing file '%s'" % (j, s.get("path")))
        cp = l.get("checkpoint")
        if cp is not None:
            if not isinstance(cp, dict) or not isinstance(cp.get("choices"), list) or len(cp["choices"]) < 2:
                rep.err(w, "checkpoint needs q, choices (2+), answer, explain")
            elif not isinstance(cp.get("answer"), int) or not 0 <= cp["answer"] < len(cp["choices"]):
                rep.err(w, "checkpoint answer must be the index of the right choice")
        check_mermaid(l.get("diagram"), w + ".diagram", rep)
    for ch, n in per_chapter.items():
        if n == 0:
            rep.warn("chapters", "chapter '%s' has no lessons" % ch)
    if core_minutes and not 40 <= core_minutes <= 65:
        rep.warn("lessons", "core lessons add up to %d minutes; aim for 45-60 so the 1-hour route tells the whole story" % core_minutes)
    for l in lessons:
        if not isinstance(l, dict):
            continue
        words = len((l.get("body") or "").split())
        if l.get("body") and not 80 <= words <= 400:
            rep.warn("lesson '%s'" % l.get("id"), "body is %d words; aim for 120-350" % words)
        cp = l.get("checkpoint")
        if isinstance(cp, dict) and not cp.get("explain"):
            rep.warn("lesson '%s'" % l.get("id"), "checkpoint has no explain")

    card_paths = set()
    for i, f in enumerate(g.get("files") or []):
        p = isinstance(f, dict) and f.get("path")
        if not p or not files.exists(p):
            rep.err("files[%d]" % i, "file card path does not exist: %s" % p)
        elif p in card_paths:
            rep.warn("files[%d]" % i, "second card for %s" % p)
        card_paths.add(p)
    for key in ("milestones", "exercises"):
        for i, m in enumerate(g.get(key) or []):
            for p in (m.get("files") or []) if isinstance(m, dict) else []:
                if not files.exists(p):
                    rep.err("%s[%d]" % (key, i), "listed file does not exist: %s" % p)
    arch = g.get("architecture") or {}
    for i, layer in enumerate(arch.get("layers") or []):
        for p in layer.get("paths") or []:
            if not files.exists(p):
                rep.err("architecture.layers[%d]" % i, "path does not exist: %s" % p)
    check_mermaid(arch.get("diagram"), "architecture.diagram", rep)
    check_mermaid((g.get("data") or {}).get("diagram"), "data.diagram", rep)
    for i, fl in enumerate(g.get("flows") or []):
        if not fl.get("id") or not SLUG.match(str(fl.get("id"))):
            rep.err("flows[%d]" % i, "flow needs a slug id")
        if not fl.get("steps"):
            rep.err("flows[%d]" % i, "flow has no steps")
    return lessons


IDENT = {"files": "path", "concepts": "term", "stack": "name", "milestones": "title", "exercises": "title",
         "decisions": "title", "risks": "title"}


def ident_of(key, item):
    field = IDENT.get(key, "id")
    return item.get(field) or item.get("id") or item.get("title") or item.get("name") or item.get("term")


def merge_fragments(g, work, rep):
    """Merge work/<key>.<name>.json arrays into the guide. Fragments win: an item whose id matches
    one already in the guide replaces it, so editing a fragment and re-running always takes effect."""
    merged = 0
    for path in sorted(glob.glob(os.path.join(work, "*.json"))):
        key = os.path.basename(path).split(".")[0]
        if key not in MERGE_KEYS:
            continue
        items = load_json(path)
        if not isinstance(items, list):
            rep.warn(os.path.basename(path), "fragment must be a JSON array; skipped")
            continue
        existing = g.setdefault(key, [])
        index = {ident_of(key, x): i for i, x in enumerate(existing) if isinstance(x, dict) and ident_of(key, x)}
        for it in items:
            if not isinstance(it, dict):
                continue
            k = ident_of(key, it)
            if not k:
                rep.warn(os.path.basename(path), "%s item has no %s; merged without de-duplication" % (key, IDENT.get(key, "id")))
                existing.append(it)
            elif k in index:
                existing[index[k]] = it
            else:
                index[k] = len(existing)
                existing.append(it)
            merged += 1
    if g.get("lessons"):
        order = {c: i for i, c in enumerate(CHAPTERS)}
        g["lessons"].sort(key=lambda l: order.get(l.get("chapter") if isinstance(l, dict) else None, 99))
    return merged


def repair_fragments(work, files, rep):
    """Apply drift fixes inside work/ fragments, so the next merge does not bring old lines back."""
    for path in sorted(glob.glob(os.path.join(work, "*.json"))):
        if os.path.basename(path).split(".")[0] not in MERGE_KEYS:
            continue
        items = load_json(path)
        changed = []

        def visit(text, where):
            def sub(m):
                scratch = Report()
                fixed = check_citation(m, where, files, scratch, {"citations": 0, "verified": 0, "files": set()})
                if fixed:
                    changed.append(fixed)
                    return fixed
                return m.group(0)
            return CITE_RE.sub(sub, text)
        walk_strings(items, os.path.basename(path), visit)
        if changed:
            save_json(path, items, indent=1)
            rep.fixed.append("%s: re-anchored %d citation(s) in the fragment" % (os.path.basename(path), len(changed)))


def verify(root, guide_path, fix=False, merge=False):
    g = load_json(guide_path)
    rep = Report()
    files = Files(root)
    work = os.path.join(os.path.dirname(guide_path), "work")
    if merge and fix:
        repair_fragments(work, files, rep)
    merged = merge_fragments(g, work, rep) if merge else 0
    lessons = check_structure(g, files, rep)
    stats = {"citations": 0, "verified": 0, "files": set()}

    def visit(text, where):
        if "]]]" in text and not CITE_RE.search(text.replace("]]]", "]]")):
            rep.warn(where, "a citation ends in ']]]'; check the anchor's brackets")
        def sub(m):
            fixed = check_citation(m, where, files, rep, stats)
            if fixed and fix:
                rep.fixed.append("%s: %s -> %s" % (where, m.group(0)[:90], fixed[:90]))
                stats["verified"] += 1
                return fixed
            if fixed:
                rep.err(where, "line numbers drifted: %s should be %s (run with --fix)" % (m.group(0)[:90], fixed[:90]))
            return m.group(0)
        return CITE_RE.sub(sub, text)

    g.pop("verification", None)  # a stale stamp never survives a re-check
    walk_strings(g, "guide", visit)
    for l in lessons:
        if isinstance(l, dict) and l.get("chapter") not in ("gist", "run", "practice") and not l.get("show") \
                and not CITE_RE.search(l.get("body", "") + (l.get("deeper") or "")):
            rep.warn("lesson '%s'" % l.get("id"), "no citations in body; ground at least one claim in code")

    head = (run_git(root, "rev-parse", "--short", "HEAD") or "").strip() or None
    result = {
        "checked_at": dt.datetime.now().isoformat(timespec="seconds"),
        "commit": head,
        "citations": stats["citations"],
        "verified": stats["verified"],
        "auto_fixed": len(rep.fixed),
        "files_cited": len(stats["files"]),
        "errors": len(rep.errors),
        "warnings": len(rep.warnings),
        "lessons": len(lessons),
    }
    rep.merged = merged
    if not rep.errors:
        g["verification"] = result
    save_json(guide_path, g, indent=1)
    return rep, result


def check_fragment(root, path):
    """Citations and paths in one fragment, for subagents writing work/ files in parallel."""
    items = load_json(path)
    if not isinstance(items, list):
        print("ERROR  %s must be a JSON array" % path)
        return 1
    key = os.path.basename(path).split(".")[0]
    rep, files = Report(), Files(root)
    stats = {"citations": 0, "verified": 0, "files": set()}
    if key == "files":
        for i, f in enumerate(items):
            if not isinstance(f, dict) or not files.exists(str(f.get("path", ""))):
                rep.err("files[%d]" % i, "file card path does not exist: %s" % (f.get("path") if isinstance(f, dict) else f))

    def visit(text, where):
        for m in CITE_RE.finditer(text):
            fixed = check_citation(m, where, files, rep, stats)
            if fixed:
                rep.err(where, "line numbers drifted: %s should be %s" % (m.group(0)[:90], fixed[:90]))
        return text
    walk_strings(items, key, visit)
    for e in rep.errors:
        print("ERROR  " + e)
    for w in rep.warnings:
        print("WARN   " + w)
    print("\n%s  %s: %d/%d citations verified, %d error(s)" % (
        "OK" if not rep.errors else "FAILED", os.path.basename(path), stats["verified"], stats["citations"], len(rep.errors)))
    return 0 if not rep.errors else 1


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("repo", nargs="?", default=".")
    ap.add_argument("--guide")
    ap.add_argument("--fix", action="store_true", help="repair drifted line numbers in place")
    ap.add_argument("--merge", action="store_true", help="merge work/<key>.*.json fragments into the guide first")
    ap.add_argument("--fragment", help="check one work/<key>.<name>.json fragment on its own (nothing is written)")
    args = ap.parse_args(argv)
    root = os.path.abspath(args.repo)
    if args.fragment:
        sys.exit(check_fragment(root, args.fragment))
    guide = args.guide or os.path.join(onramp_dir(root), "guide.json")
    if not os.path.exists(guide):
        sys.exit("onramp: no guide at %s" % guide)
    rep, res = verify(root, guide, fix=args.fix, merge=args.merge)
    if args.merge:
        print("merged %d item(s) from work/ fragments" % rep.merged)
    for f in rep.fixed[:60]:
        print("FIXED  " + f)
    for w in rep.warnings[:60]:
        print("WARN   " + w)
    for e in rep.errors[:120]:
        print("ERROR  " + e)
    if len(rep.errors) > 120:
        print("... %d more errors" % (len(rep.errors) - 120))
    status = "OK" if not rep.errors else "FAILED"
    print("\n%s  %d/%d citations verified across %d files, %d auto-fixed, %d error(s), %d warning(s), %d lessons" % (
        status, res["verified"], res["citations"], res["files_cited"], res["auto_fixed"], res["errors"], res["warnings"], res["lessons"]))
    sys.exit(0 if not rep.errors else 1)


if __name__ == "__main__":
    main()
