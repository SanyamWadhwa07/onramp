#!/usr/bin/env python3
"""Build the website's live demos and the landing page's route preview.

usage: python docs/build.py <repo> <name> [<repo> <name> ...]

Each repo must already have a verified .onramp/guide.json. Its guide is rendered with --public
into docs/demo/<name>/. The first repo also feeds docs/assets/sample-route.js, the real route
numbers shown by the planner on the landing page (same rules as the viewer's planner).
"""
import json
import os
import sys

DOCS = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(DOCS), "skills", "onramp", "scripts"))
import render  # noqa: E402

TIMES = {"h1": (60, ["The hour"]), "d1": (360, ["Morning", "Midday", "Afternoon"]),
         "d3": (900, ["Day 1", "Day 2", "Day 3"]), "w1": (1500, ["Day 1", "Day 2", "Day 3", "Day 4", "Day 5"])}
ORDER = {  # same as the viewer
    "gist": ["gist", "map", "stack", "concepts", "flows", "data", "why", "built", "files", "care", "run", "practice"],
    "ship": ["gist", "run", "map", "flows", "files", "care", "practice", "stack", "concepts", "data", "why", "built"],
    "own": ["gist", "run", "stack", "map", "concepts", "flows", "data", "files", "built", "why", "care", "practice"],
    "rebuild": ["gist", "stack", "built", "map", "concepts", "data", "flows", "files", "why", "care", "run", "practice"],
}
SAMPLE_GOAL = "own"
CHAPTERS = ["gist", "run", "stack", "map", "concepts", "flows", "data", "files", "built", "why", "care", "practice"]
SHORT = {"gist": "the gist", "run": "running it", "stack": "the stack", "map": "the map", "concepts": "core ideas",
         "flows": "the flows", "data": "the data", "files": "the files", "built": "how it was built",
         "why": "the why", "care": "the risks", "practice": "practice"}


def extras(guide, scan):
    """The viewer's hands-on stops (see EXTRAS in viewer.js): exercises, milestones, file reads."""
    lines = {f["path"]: f.get("lines", 0) for f in scan.get("files", [])}
    out = []
    for i, x in enumerate(guide.get("exercises") or []):
        out.append({"id": "do-exercise-%d" % (i + 1), "chapter": "practice", "tier": "deep", "extra": True,
                    "minutes": {"easy": 30, "medium": 60, "hard": 120}.get(x.get("level"), 45),
                    "goals": ["ship", "own", "rebuild"], "title": "Do it: " + x.get("title", "")})
    for i, m in enumerate(guide.get("milestones") or []):
        if m.get("try"):
            out.append({"id": "build-milestone-%d" % (i + 1), "chapter": "built", "tier": "deep", "extra": True,
                        "minutes": 60, "goals": ["rebuild"], "title": "Build it: " + m.get("title", "")})
    for c in guide.get("files") or []:
        n = lines.get(c.get("path"), 0)
        if n:
            out.append({"id": "read-" + c["path"], "chapter": "files", "tier": "deep", "extra": True,
                        "minutes": max(10, min(60, int(n / 30 + 0.5))), "goals": ["gist", "own", "ship", "rebuild"],
                        "title": "Read " + c["path"]})
    return out


def route(lessons, time, goal="gist", bg="know"):
    budget, seg_names = TIMES[time]
    order = ORDER[goal]
    tier_p = {"core": 30, "standard": 20, "deep": 10}

    def weight(ch):
        return max(0, 6 - order.index(ch) // 2) if ch in order else 0

    cands = []
    for i, l in enumerate(lessons):
        if l.get("for") and bg not in l["for"]:
            continue
        if l.get("extra") and goal not in l["goals"]:
            continue
        serves = not l.get("goals") or goal in l["goals"]
        base = 5 if l.get("extra") else tier_p.get(l.get("tier"), 10)
        cands.append({"l": l, "i": i, "mins": max(1, round(l.get("minutes", 5))),
                      "pr": base + (8 if serves else 0) + weight(l.get("chapter"))})
    key = lambda c: (-c["pr"], c["i"])  # noqa: E731
    used, picked = 0, []
    for c in sorted((c for c in cands if c["l"].get("tier") == "core"), key=key):
        if used + c["mins"] <= budget or not picked:
            picked.append(c)
            used += c["mins"]
    for c in sorted((c for c in cands if c["l"].get("tier") != "core"), key=key):
        if used + c["mins"] <= budget:
            picked.append(c)
            used += c["mins"]
    picked.sort(key=lambda c: (order.index(c["l"]["chapter"]) if c["l"]["chapter"] in order else 99, c["i"]))
    n, segs = len(seg_names), []
    cap = used / n
    cur = {"name": seg_names[0], "stops": [], "mins": 0}
    for s in picked:
        if cur["stops"] and cur["mins"] + s["mins"] / 2 > cap and len(segs) < n - 1:
            segs.append(cur)
            cur = {"name": seg_names[len(segs)], "stops": [], "mins": 0}
        cur["stops"].append(s)
        cur["mins"] += s["mins"]
    segs.append(cur)
    days = []
    for sg in segs:
        seen = []
        for s in sg["stops"]:
            short = SHORT.get(s["l"]["chapter"])
            if short and short not in seen:
                seen.append(short)
        if len(seen) > 3:
            title = ", ".join(seen[:3]) + " and more"
        else:
            title = seen[0] if len(seen) == 1 else ", ".join(seen[:-1]) + " and " + seen[-1]
        title = title[:1].upper() + title[1:]
        days.append({"name": sg["name"], "title": title, "n": len(sg["stops"]), "mins": sg["mins"]})
    first = [["%02d" % (CHAPTERS.index(s["l"]["chapter"]) + 1), s["l"]["title"], s["mins"]] for s in picked[:3]]
    return {"mins": used, "stops": len(picked), "days": days, "first": first}


ANALYTICS = ('<script>window.va = window.va || function () { (window.vaq = window.vaq || []).push(arguments); };</script>\n'
             '<script defer src="/_vercel/insights/script.js"></script>\n')


def add_analytics(html_path):
    """Published demos count page views; guides people build locally never carry analytics."""
    with open(html_path, encoding="utf-8") as fh:
        html = fh.read()
    if "/_vercel/insights/script.js" not in html:
        html = html.replace("</head>", ANALYTICS + "</head>", 1)
        with open(html_path, "w", encoding="utf-8") as fh:
            fh.write(html)


def label(scan):
    """A neutral description of the demo codebase, e.g. 'a 31,575-line Python + JavaScript codebase'."""
    langs = [l["lang"] for l in scan.get("languages", [])[:2] if l.get("share", 0) >= 10]
    lines = (scan.get("summary") or {}).get("lines", 0)
    return "a %s-line %s codebase" % ("{:,}".format(lines), " + ".join(langs) or "")


def main(argv):
    if len(argv) < 2 or len(argv) % 2:
        sys.exit(__doc__)
    for k in range(0, len(argv), 2):
        repo, name = os.path.abspath(argv[k]), argv[k + 1]
        out = os.path.join(DOCS, "demo", name)
        render.main([repo, "--public", "--out", out])
        add_analytics(os.path.join(out, "index.html"))
        if k == 0:
            with open(os.path.join(repo, ".onramp", "guide.json"), encoding="utf-8") as fh:
                guide = json.load(fh)
            with open(os.path.join(repo, ".onramp", "scan.json"), encoding="utf-8") as fh:
                scan = json.load(fh)
            sample = {"name": guide["project"]["name"], "label": label(scan),
                      "goal": SAMPLE_GOAL,
                      "routes": {t: route(guide["lessons"] + extras(guide, scan), t, SAMPLE_GOAL) for t in TIMES},
                      "verification": guide.get("verification")}
            with open(os.path.join(DOCS, "assets", "sample-route.js"), "w", encoding="utf-8") as fh:
                fh.write("// Generated by docs/build.py from the %s demo guide.\nwindow.ONRAMP_SAMPLE = %s;\n"
                         % (name, json.dumps(sample, ensure_ascii=False, indent=1)))
            print("sample route  docs/assets/sample-route.js (%s)" % ", ".join(
                "%s: %d stops" % (t, r["stops"]) for t, r in sample["routes"].items()))


if __name__ == "__main__":
    main(sys.argv[1:])
