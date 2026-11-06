#!/usr/bin/env python3
"""Digest Claude Code transcripts for this project into .onramp/work/sessions.json.

Recovers *why* files exist: for every file Claude wrote or edited, the prompt that led to it
and the explanation Claude gave just before the edit. Reads local files only. Secrets that look
like API keys or tokens are redacted.

usage: sessions.py [repo] [--out PATH]
"""
import argparse
import json
import os
import re
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import claude_project_dirs, onramp_dir, posix, save_json  # noqa: E402

EDIT_TOOLS = {"Write", "Edit", "MultiEdit", "NotebookEdit", "str_replace_based_edit_tool"}
NOISE = ("<command-", "<local-command", "Caveat:", "[Request interrupted", "<bash-", "<task-notification")
SECRET = re.compile(
    r"(sk-[A-Za-z0-9_\-]{16,}|gh[pousr]_[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|xox[abpr]-[A-Za-z0-9\-]{10,}"
    r"|AIza[0-9A-Za-z_\-]{30,}|eyJ[A-Za-z0-9_\-]{20,}\.[A-Za-z0-9_\-]{10,}\.[A-Za-z0-9_\-]{10,}"
    r"|(?<![A-Za-z0-9])[A-Fa-f0-9]{40,}(?![A-Za-z0-9]))"
)
REMINDER = re.compile(r"<(system-reminder|ide_[a-z_]+|browser_[a-z_]+|command-[a-z]+|local-command-[a-z]+|"
                      r"user-prompt-submit-hook|attachment)\b[^>]*>.*?</\1>", re.S)


def clean(text, limit):
    text = REMINDER.sub("", text or "")
    text = SECRET.sub("[redacted]", text)
    text = re.sub(r"\s+\n", "\n", text).strip()
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def user_text(msg):
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content if isinstance(b, dict) and b.get("type") == "text")
    return ""


def rel_path(root_norm, file_path):
    if not file_path:
        return None
    full = os.path.normcase(os.path.abspath(file_path))
    if full == root_norm or not full.startswith(root_norm + os.sep):
        return None
    return posix(os.path.relpath(os.path.abspath(file_path), os.path.dirname(root_norm + os.sep)))


def digest(root):
    root_abs = os.path.abspath(root).rstrip("\\/")
    root_norm = os.path.normcase(root_abs)
    sessions, per_file = [], defaultdict(list)
    for d in claude_project_dirs(root):
        for name in sorted(os.listdir(d)):
            if not name.endswith(".jsonl"):
                continue
            sid = name[:-6]
            sess = {"id": sid[:8], "title": None, "start": None, "end": None, "prompts": [], "edits": 0}
            prompt, why = None, None
            with open(os.path.join(d, name), encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    try:
                        o = json.loads(line)
                    except ValueError:
                        continue
                    t = o.get("type")
                    if t == "ai-title" and o.get("aiTitle"):
                        sess["title"] = clean(o["aiTitle"], 120)
                    if t not in ("user", "assistant") or o.get("isSidechain") or o.get("isMeta"):
                        continue
                    ts = (o.get("timestamp") or "")[:16].replace("T", " ")
                    if ts:
                        sess["start"] = sess["start"] or ts
                        sess["end"] = ts
                    msg = o.get("message") or {}
                    if t == "user":
                        text = clean(user_text(msg), 700)
                        if not text or text.startswith(NOISE):
                            continue
                        prompt, why = text, None
                        if len(sess["prompts"]) < 60:
                            sess["prompts"].append({"at": ts, "text": text})
                        continue
                    for block in msg.get("content") or []:
                        if not isinstance(block, dict):
                            continue
                        if block.get("type") == "text" and block.get("text", "").strip():
                            why = clean(block["text"], 500)
                        elif block.get("type") == "tool_use" and block.get("name") in EDIT_TOOLS:
                            inp = block.get("input") or {}
                            rel = rel_path(root_norm, inp.get("file_path") or inp.get("notebook_path") or inp.get("path"))
                            if not rel:
                                continue
                            sess["edits"] += 1
                            per_file[rel].append({
                                "at": ts, "session": sid[:8], "tool": block["name"],
                                "prompt": (prompt or "")[:400], "why": why or "",
                            })
            if sess["prompts"] or sess["edits"]:
                sessions.append(sess)
    sessions.sort(key=lambda s: s["start"] or "")
    files = {}
    for path, events in per_file.items():
        events.sort(key=lambda e: e["at"])
        keep = events[:1] + events[1:][-5:]
        files[path] = {"edits": len(events), "first": events[0]["at"], "last": events[-1]["at"], "events": keep}
    return {
        "root": root_abs,
        "sessions": sessions,
        "files": dict(sorted(files.items(), key=lambda kv: -kv[1]["edits"])),
        "stats": {"sessions": len(sessions), "prompts": sum(len(s["prompts"]) for s in sessions),
                  "files_touched": len(files), "edits": sum(f["edits"] for f in files.values())},
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("repo", nargs="?", default=".")
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    data = digest(args.repo)
    out = args.out or os.path.join(onramp_dir(args.repo), "work", "sessions.json")
    save_json(out, data, indent=1)
    s = data["stats"]
    print("ONRAMP SESSIONS  %d session(s), %d prompt(s), %d edit(s) across %d file(s)  ->  %s" % (
        s["sessions"], s["prompts"], s["edits"], s["files_touched"], out))
    for sess in data["sessions"][:20]:
        print("  %s  %s  %s  (%d prompts, %d edits)" % (sess["start"], sess["id"], sess["title"] or "", len(sess["prompts"]), sess["edits"]))
    for path, info in list(data["files"].items())[:25]:
        print("  %3d edits  %s" % (info["edits"], path))


if __name__ == "__main__":
    main()
