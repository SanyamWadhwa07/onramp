#!/usr/bin/env python3
"""Render .onramp/guide.json into a single self-contained index.html and a GUIDE.md.

The page embeds the real code behind every citation (read from disk now, never written by the
model), the scanner's dependency graph and history, and the route planner. It opens from disk
with no server; diagrams and syntax colours load from a CDN when online.

usage: render.py [repo] [--guide PATH] [--out DIR] [--open] [--with-sessions] [--public]
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
import webbrowser
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import CITE_RE, VERSION, load_json, onramp_dir, read_lines, save_json  # noqa: E402

ASSETS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "assets")
CONTEXT = 3
MAX_SNIPPET = 140
MAX_SOURCE_LINES = 4000
SOURCE_BUDGET = 8_000_000
CHAPTER_TITLES = [
    ("gist", "The gist"), ("run", "Run it"), ("stack", "The stack"), ("map", "The map"),
    ("concepts", "Core ideas"), ("flows", "How it flows"), ("data", "Data and state"),
    ("files", "File by file"), ("built", "How it was built"), ("why", "Why it's like this"),
    ("care", "Handle with care"), ("practice", "Your first changes"),
]


def iter_strings(node):
    if isinstance(node, dict):
        for v in node.values():
            yield from iter_strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from iter_strings(v)
    elif isinstance(node, str):
        yield node


def collect(guide, root):
    """Snippets for every line citation, plus the set of files the guide mentions."""
    snippets, mentioned, cache = {}, set(), {}
    for text in iter_strings(guide):
        for m in CITE_RE.finditer(text):
            path = m.group(1).strip()
            mentioned.add(path)
            if not m.group(2):
                continue
            start = int(m.group(2))
            end = int(m.group(3) or start)
            key = "%s:%d-%d" % (path, start, end)
            if key in snippets:
                continue
            if path not in cache:
                cache[path] = read_lines(os.path.join(root, path))
            lines = cache[path]
            if not lines:
                continue
            lo = max(1, start - CONTEXT)
            hi = min(len(lines), end + CONTEXT, lo + MAX_SNIPPET - 1)
            snippets[key] = {"path": path, "start": start, "end": end, "from": lo,
                             "code": "\n".join(lines[lo - 1:hi]), "total": len(lines)}
    for f in guide.get("files") or []:
        if isinstance(f, dict) and f.get("path"):
            mentioned.add(f["path"])
    return snippets, mentioned


def slim_scan(scan):
    used_by = {}
    for f in scan.get("files", []):
        for i in f.get("imports", []):
            used_by.setdefault(i, []).append(f["path"])
    files = []
    for f in scan.get("files", []):
        if f["kind"] in ("lock",):
            continue
        row = {"p": f["path"], "l": f["lang"], "k": f["kind"], "n": f["lines"], "s": f.get("score", 0)}
        if f.get("imports"):
            row["i"] = f["imports"]
        if used_by.get(f["path"]):
            row["u"] = sorted(used_by[f["path"]])
        if f.get("churn"):
            row["c"] = f["churn"]
        if f.get("sha1"):
            row["h"] = f["sha1"]
        files.append(row)
    git = scan.get("git") or {}
    return {
        "name": scan.get("name"),
        "summary": scan.get("summary"),
        "languages": scan.get("languages"),
        "entrypoints": scan.get("entrypoints"),
        "modules": scan.get("modules"),
        "module_edges": scan.get("module_edges"),
        "env_vars": scan.get("env_vars"),
        "todos": (scan.get("todos") or [])[:80],
        "external_packages": (scan.get("external_packages") or [])[:40],
        "git": dict({k: git.get(k) for k in ("is_repo", "short", "head", "branch", "github", "commits", "authors",
                                              "first_commit", "last_commit", "timeline", "dirty")},
                    log=[{k: c[k] for k in ("hash", "date", "subject", "files")} for c in (git.get("log") or [])[:120]]),
        "sessions": {k: (scan.get("sessions") or {}).get(k) for k in ("found", "count", "first", "last")},
        "files": files,
    }


def embed_sources(root, paths, scan_files):
    sizes = {f["path"]: f for f in scan_files}
    out, budget = {}, SOURCE_BUDGET
    for p in sorted(paths, key=lambda x: -(sizes.get(x, {}).get("score") or 0)):
        meta = sizes.get(p)
        if not meta or meta.get("lines", 0) > MAX_SOURCE_LINES or meta["kind"] in ("asset", "data", "lock"):
            continue
        lines = read_lines(os.path.join(root, p))
        if lines is None:
            continue
        text = "\n".join(lines)
        if len(text) > budget:
            break
        budget -= len(text)
        out[p] = text
    return out


def to_script_json(data):
    return json.dumps(data, ensure_ascii=False, separators=(",", ":")) \
        .replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")


def esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def build_html(payload, guide):
    with open(os.path.join(ASSETS, "viewer.html"), encoding="utf-8") as fh:
        html = fh.read()
    with open(os.path.join(ASSETS, "viewer.css"), encoding="utf-8") as fh:
        css = fh.read()
    with open(os.path.join(ASSETS, "viewer.js"), encoding="utf-8") as fh:
        js = fh.read()
    proj = guide.get("project") or {}
    parts = {
        "TITLE": esc(proj.get("name") or "Project") + " guide",
        "DESCRIPTION": esc(proj.get("one_liner") or ""),
        "CSS": css, "DATA": to_script_json(payload), "JS": js,
    }
    # one pass over the template only, so inserted content is never re-scanned for markers
    return re.sub(r"/\*ONRAMP:(CSS|DATA|JS)\*/|\{\{(TITLE|DESCRIPTION)\}\}",
                  lambda m: parts[m.group(1) or m.group(2)], html)


# ---------------------------------------------------------------- markdown export

def md_links(text, link):
    def sub(m):
        path, s, e = m.group(1).strip(), m.group(2), m.group(3)
        label = path + (":%s" % s if s else "") + ("-%s" % e if e else "")
        return "[`%s`](%s)" % (label, link(path, s, e))
    return CITE_RE.sub(sub, text or "")


def build_markdown(guide, scan, github, commit):
    proj = guide.get("project") or {}
    ver = guide.get("verification") or {}

    def link(path, s, e):
        anchor = ""
        if s:
            anchor = "#L%s" % s + ("-L%s" % e if e and e != s else "")
        if github and commit:
            return "%s/blob/%s/%s%s" % (github, commit, path, anchor)
        return "../%s%s" % (path, anchor)

    L = lambda t: md_links(t, link)  # noqa: E731
    out = ["# %s" % proj.get("name", "Project"), "", "> %s" % proj.get("one_liner", ""), ""]
    if ver:
        out += ["**%d/%d citations verified** against the code at `%s` on %s. Generated by [Onramp](https://github.com/SanyamWadhwa07/onramp)." % (
            ver.get("verified", 0), ver.get("citations", 0), ver.get("commit") or "working tree", (ver.get("checked_at") or "")[:10]), ""]
    if proj.get("what"):
        out += [L(proj["what"]), ""]
    if proj.get("analogy"):
        out += ["*In one picture:* " + L(proj["analogy"]), ""]
    lessons = guide.get("lessons") or []
    out += ["## Contents", ""]
    for i, (cid, title) in enumerate(CHAPTER_TITLES, 1):
        n = sum(1 for l in lessons if l.get("chapter") == cid)
        if n:
            out.append("%d. [%s](#%s) (%d)" % (i, title, re.sub(r"[^a-z0-9 -]", "", title.lower()).replace(" ", "-"), n))
    out.append("")
    for cid, title in CHAPTER_TITLES:
        ch = [l for l in lessons if l.get("chapter") == cid]
        if not ch:
            continue
        out += ["## %s" % title, ""]
        for l in ch:
            out += ["### %s" % l.get("title", ""), "",
                    "*%s · %s min*" % (l.get("tier", ""), l.get("minutes", "")), "",
                    "**In short:** " + L(l.get("summary")), "", L(l.get("body")), ""]
            if l.get("deeper"):
                out += ["<details><summary>Go deeper</summary>", "", L(l["deeper"]), "", "</details>", ""]
            for view in l.get("show") or []:
                if view.get("view") == "flow":
                    fl = next((f for f in guide.get("flows") or [] if f.get("id") == view.get("id")), None)
                    if fl:
                        out += ["**Flow: %s**%s" % (fl.get("title", ""), (" (trigger: %s)" % fl["trigger"]) if fl.get("trigger") else ""), ""]
                        for k, st in enumerate(fl.get("steps") or [], 1):
                            out.append("%d. **%s** %s %s" % (k, st.get("title", ""), L(st.get("at")), L(st.get("explain"))))
                        out.append("")
            cp = l.get("checkpoint")
            if cp:
                out += ["> **Checkpoint:** %s" % cp.get("q", "")]
                for k, c in enumerate(cp.get("choices") or []):
                    out.append("> - %s" % c)
                out += [">", "> <details><summary>Answer</summary>%s. %s</details>" % (
                    (cp.get("choices") or ["?"])[cp.get("answer", 0)], L(cp.get("explain"))), ""]
    appendix = []
    if guide.get("stack"):
        appendix += ["### Stack", "", "| Technology | Role | Where |", "|---|---|---|"]
        for s in guide["stack"]:
            appendix.append("| %s | %s | %s |" % (s.get("name", ""), L(s.get("role", "")).replace("\n", " "), L(s.get("where", ""))))
        appendix.append("")
    if guide.get("files"):
        appendix += ["### Files", ""]
        for f in guide["files"]:
            appendix.append("- [`%s`](%s): %s" % (f["path"], link(f["path"], None, None), L(f.get("role") or f.get("summary") or "")))
        appendix.append("")
    if guide.get("concepts"):
        appendix += ["### Glossary", ""]
        for c in guide["concepts"]:
            appendix.append("- **%s**: %s %s" % (c.get("term", ""), L(c.get("plain", "")), L(c.get("at", ""))))
        appendix.append("")
    if appendix:
        out += ["## Reference", ""] + appendix
    out += ["---", "", "Generated with [Onramp](https://github.com/SanyamWadhwa07/onramp) on %s." % dt.date.today().isoformat(), ""]
    return "\n".join(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("repo", nargs="?", default=".")
    ap.add_argument("--guide")
    ap.add_argument("--out", help="output directory (default <repo>/.onramp)")
    ap.add_argument("--open", action="store_true", help="open the guide in the browser")
    ap.add_argument("--with-sessions", action="store_true", help="show Claude Code history on file cards")
    ap.add_argument("--public", action="store_true", help="omit the local path; link code to GitHub")
    args = ap.parse_args(argv)
    root = os.path.abspath(args.repo)
    base = onramp_dir(root)
    guide = load_json(args.guide or os.path.join(base, "guide.json"))
    scan_path = os.path.join(base, "scan.json")
    if not os.path.exists(scan_path):
        sys.exit("onramp: run scan.py first (missing %s)" % scan_path)
    scan = load_json(scan_path)
    if not guide.get("verification"):
        print("note: guide has no verification stamp; run verify.py first for the trust badge")

    snippets, mentioned = collect(guide, root)
    sources = embed_sources(root, mentioned, scan.get("files", []))
    git = scan.get("git") or {}
    sessions = None
    sess_path = os.path.join(base, "work", "sessions.json")
    if args.with_sessions and os.path.exists(sess_path):
        sd = load_json(sess_path)
        sessions = {"files": sd.get("files", {}), "sessions": [
            dict({k: s.get(k) for k in ("id", "title", "start", "end")}, prompts=len(s.get("prompts", [])))
            for s in sd.get("sessions", [])]}
    payload = {
        "guide": guide,
        "scan": slim_scan(scan),
        "snippets": snippets,
        "sources": sources,
        "sessions": sessions,
        "meta": {
            "tool": "Onramp", "version": VERSION, "rendered_at": dt.datetime.now().isoformat(timespec="seconds"),
            "root": None if args.public else root, "github": git.get("github"),
            "commit": git.get("head"), "public": bool(args.public),
        },
    }
    out_dir = os.path.abspath(args.out or base)
    os.makedirs(out_dir, exist_ok=True)
    html_path = os.path.join(out_dir, "index.html")
    with open(html_path, "w", encoding="utf-8") as fh:
        fh.write(build_html(payload, guide))
    with open(os.path.join(out_dir, "GUIDE.md"), "w", encoding="utf-8") as fh:
        fh.write(build_markdown(guide, scan, git.get("github") if args.public else None, git.get("head")))
    ver = guide.get("verification") or {}
    print("ONRAMP RENDER  %s  (%.0f KB, %d lessons, %d code excerpts, %d embedded files%s)" % (
        html_path, os.path.getsize(html_path) / 1024, len(guide.get("lessons") or []), len(snippets), len(sources),
        (", %d/%d citations verified" % (ver.get("verified", 0), ver.get("citations", 0))) if ver else ""))
    print("markdown      %s" % os.path.join(out_dir, "GUIDE.md"))
    if args.open:
        webbrowser.open(Path(html_path).as_uri())


if __name__ == "__main__":
    main()
