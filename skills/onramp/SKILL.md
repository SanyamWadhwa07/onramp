---
name: onramp
description: Turns any codebase into a personal learning route. Produces a single-page guide that plans a route for the reader's time (1 hour to 1 week) and goal, then walks them through what the project does, how to run it, its stack, architecture, request flows, data, key files, how it was built and why. Every claim is cited to real lines of code and checked by a script. Use when someone wants to understand, onboard onto, learn, review or explain a repository, including a project an AI coding agent built for them ("explain this codebase", "walk me through this repo", "how does this project work", "I don't understand what was built").
license: MIT
compatibility: Any agent that can read files and run Python 3.8+ (standard library only). Tested most in Claude Code.
metadata:
  version: "1.0.2"
  homepage: "https://onramp-skill.vercel.app"
allowed-tools: Read Grep Glob Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/scan.py *) Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/sessions.py *) Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/verify.py *) Bash(python3 ${CLAUDE_SKILL_DIR}/scripts/render.py *) Bash(python ${CLAUDE_SKILL_DIR}/scripts/scan.py *) Bash(python ${CLAUDE_SKILL_DIR}/scripts/sessions.py *) Bash(python ${CLAUDE_SKILL_DIR}/scripts/verify.py *) Bash(python ${CLAUDE_SKILL_DIR}/scripts/render.py *) Bash(py -3 ${CLAUDE_SKILL_DIR}/scripts/scan.py *) Bash(py -3 ${CLAUDE_SKILL_DIR}/scripts/sessions.py *) Bash(py -3 ${CLAUDE_SKILL_DIR}/scripts/verify.py *) Bash(py -3 ${CLAUDE_SKILL_DIR}/scripts/render.py *)
---

# Onramp

You turn a codebase into a guide the reader can actually learn from: a route through the
project sized to the time they have, where every technical claim links to the real code and a
script has checked that the code says what the guide says.

Output lives in `<repo>/.onramp/`: `index.html` (the interactive guide), `GUIDE.md` (the same
content as markdown, for GitHub and for agents), `guide.json` (the source), `scan.json`.

## Setup

This skill works in any agent that can read files and run commands.

- Scripts live in the `scripts/` folder next to this file. In Claude Code that is
  `${CLAUDE_SKILL_DIR}/scripts/`.
- Python 3.8+, standard library only. Use `python3`; on Windows use `python` or `py -3`.
- Below, `$S` means the scripts folder and `<repo>` the project root (default: the current
  directory).
- Before writing `guide.json`, read [reference/schema.md](reference/schema.md) (the contract)
  and [reference/writing.md](reference/writing.md) (how to write it).

## Choose the mode

Take the mode from the user's request. In Claude Code the slash-command arguments are:
`$ARGUMENTS`

| Request | Mode |
|---|---|
| empty, or a path | **full guide** for that path |
| `quick [path]` | **quick**: core lessons only (the 1-hour route), much cheaper |
| `explain <file, folder or symbol>` | **explain**: one deep lesson, added to the guide |
| `trace "<user action>"` | **trace**: one traced flow, added to the guide |
| `update` | **update**: refresh a guide after the code changed |
| `tutor` | **tutor**: teach the route in this chat, one stop at a time |

## Full guide

Tell the user what you are doing at each step in one short line. A full guide on a mid-size repo
takes a while; that is expected.

### 1. Scan

```
python3 $S/scan.py <repo>
```

Read the printed summary: languages, manifests, entry points, the ranked "read first" list,
module edges, env vars, git history, Claude sessions. If it lists files deleted but not
committed, they cannot be cited: describe the working tree as it is and note the deletion in
the `care` chapter. `.onramp/scan.json` has the full detail;
query it with short Python or grep instead of reading the whole file.

### 2. Ask about agent history (only if the scan found sessions)

The scanner looks for Claude Code transcripts of this project. If it found some, ask once:
"I found N Claude Code sessions for this project. Should I use them to explain why things were
built? They stay on your machine, and quotes appear in the guide only if you keep them."
Claude Code deletes transcripts after about 30 days by default, so older projects may have
little. Other agents' histories are not read yet; git history covers them.

If yes: `python3 $S/sessions.py <repo>` and use `.onramp/work/sessions.json` as evidence for
the `why` and `built` chapters (quote prompts briefly, mark those decisions `documented`).
If no answer is possible (non-interactive run), skip it.

### 3. Read the code, in this order

1. `README`, `CLAUDE.md`/`AGENTS.md`, docs listed by the scan.
2. Manifests and config: how it is installed, run, built, deployed.
3. Entry points, then the top of the "read first" ranking.
4. For each important user action, follow the calls from the entry point to storage and back.

Open every file you describe. Never describe a file, function or behaviour you have not read.
Note exact line numbers as you read; you need them for citations.

**Large repos** (more than about 120 source files): if your agent can start subagents, fan
out; otherwise work through the modules one at a time in the same way. Brief each subagent with
the template in [reference/fanout.md](reference/fanout.md). Each one writes
`.onramp/work/files.<module>.json` and checks it with `verify.py <repo> --fragment <file>`.
You still read the entry points and trace the flows yourself.

### 4. Write the guide

Write `.onramp/guide.json` per the schema. To keep tool calls manageable, write the top-level
sections first, then lessons chapter by chapter as `.onramp/work/lessons.<chapter>.json` arrays
(merged by `verify.py --merge`; lessons are put in chapter order and a fragment always replaces
the item it was merged as, so edit fragments, not the merged copy). Long markdown is easier to
produce with a short Python script that builds the structure and calls `json.dump` than by
escaping quotes and newlines by hand.

What a complete guide contains:
- **20–40 lessons covering all 12 chapters.** Core lessons add up to 45–60 minutes and alone
  tell the whole story: what it is, how to run it, the map, the main flow, where to be careful.
- **Stack primers** (`for: ["new"]`) for each major technology, so other lessons can assume it.
- **2–5 flows**: real user actions traced step by step, each step citing the exact function.
- **File cards** for every file a newcomer would need to open (typically 15–60).
- **Milestones**: the order you would build this project in, foundations first (use the
  scan's import graph: files nothing depends on come last). Each with a hands-on `try`.
- **Decisions**: why things are the way they are, each marked `documented` (you have a commit,
  doc, comment or session quote) or `inferred` (your reasoning from the code).
- **Risks**: what is fragile, untested, insecure or confusing, with the exact place.
- **Exercises**: 4–8 real changes from easy to hard.
- **Checkpoints** on about half the lessons.

Citations: `[[path:start-end|anchor]]` where the anchor is text copied exactly from those
lines. Cite the lines that prove the claim, not the whole file.

### 5. Verify (required)

```
python3 $S/verify.py <repo> --merge --fix
```

Repeat until it prints `OK`. For every `ERROR`, open the cited file, find what the code really
says, and fix the citation or rewrite the claim. Never weaken an anchor or remove a citation
just to pass; an unverifiable claim gets deleted, not hidden. Fix warnings when they point at
real gaps (uncited lessons, empty chapters).

### 6. Render

```
python3 $S/render.py <repo> --open
```

Add `--with-sessions` only if the user agreed in step 2 (shows session history on file cards).
Add `--public` when the guide will be published (drops the local path; code links go to GitHub).

### 7. Report

In a few lines: where the guide is, the verification line (for example "212/212 citations
verified at a1b2c3d"), and the two or three things about this codebase most worth knowing.
Tell them to open the guide and plan a route, and mention the tutor mode (`/onramp tutor` in
Claude Code, or "use onramp as a tutor" in other agents). Suggest adding
`.onramp/` to `.gitignore` (or committing `GUIDE.md` if the team wants it).

## Other modes

**quick**: steps 1, 3, 4 and 5 with only `core` lessons (and the sections they show). Skip the
history question. Then render.

**explain `<target>`**: run the scan if `.onramp/scan.json` is missing. Read the target and
everything it calls and is called by. Answer in chat (short, with file:line references), then add
a lesson (chapter `files` or `concepts`, tier `deep`) and its file cards to the guide, verify and
render. If there is no guide yet, write a minimal one (project + this lesson).

**trace `"<action>"`**: find where the action starts (UI handler, CLI command, route), follow
every call to storage and back, and add it as a flow plus a `flows` lesson that shows it. Answer
in chat with the numbered path, then verify and render.

**update**: re-run the scan, compare each cited file's `sha1` in the new `scan.json` with
`.onramp/scan.json` from before (copy the old one first), list the changed and new files, re-read
them, update the affected lessons, cards and flows, then verify and render. Report what changed.

**tutor**: teach the route in chat.
1. If `.onramp/guide.json` is missing, offer to build the guide first (quick mode is fine).
2. If `.onramp/progress.json` exists, offer to continue. Otherwise ask the three route questions
   (time, goal, background) and build the route with the rules at the end of
   `reference/schema.md`. Show the itinerary: days, stops, minutes.
3. One stop per message: the summary, the explanation in plain words with one or two short real
   excerpts (read the cited lines; never paste invented code), then the checkpoint question.
   Wait for the answer, give feedback with the reason, save progress to `.onramp/progress.json`
   (`{"route": {...}, "done": ["lesson-id", ...], "score": [right, asked]}`), and offer the next stop.
4. Answer side questions from the code, then return to the route.

## Rules

- Write only inside `<repo>/.onramp/`. Never modify the user's code in any mode.
- Every technical claim is grounded in code you opened. When you are inferring, say so.
- Explain in plain words before using a term (see `reference/writing.md`).
- Be honest about weaknesses in the code; do not invent them either.
- Do not put secrets, tokens or personal data from the repo or the sessions into the guide.
- If the repo is huge, go broad on the map and deep on the main flows; say what you skipped.
