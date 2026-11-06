# Subagent brief for file cards

On large repositories, give each subagent one or two modules and a brief built from this
template. Fill in the bracketed parts. Keep the area names identical across briefs so the cards
group cleanly in the viewer.

```
You are writing file cards for an Onramp guide of the repository at <repo>.
Your modules: <module paths from the scan>.
Area names to use (pick one per card): <e.g. "API", "Agents", "Pipeline", "Frontend", "Data">.

Read reference/schema.md sections "Citations" and "files", and reference/writing.md.
Open every file you write about. Never describe code you have not read.

For each file a newcomer would need to open (usually 5-15 per module), write a card:
  path, area, role (one line), summary (2-5 sentences), symbols (the 2-5 functions or classes
  that matter, each with an "at" citation and "does"), read_when, complexity (1-5), gotchas
  (optional). Every claim about code carries a [[path:start-end|anchor]] citation whose anchor is
  copied exactly from those lines.

Write a JSON array to <repo>/.onramp/work/files.<module>.json. Generate the JSON with a short
Python script (json.dump) rather than escaping long text by hand.

Before you finish, check your file:
  python <scripts>/verify.py <repo> --fragment <repo>/.onramp/work/files.<module>.json
Fix every ERROR. Do not weaken an anchor to make it pass; rewrite the claim from the code.

Paths that are deleted in the working tree cannot be cited: <list from the scan, if any>.

Reply with: the card count, the verify line, and three facts about your modules the main
guide should know (each with a citation).
```

The main agent still reads the entry points and traces the flows itself; subagents only write
file cards (and, if asked, `concepts.<module>.json` entries keyed by `term`).
