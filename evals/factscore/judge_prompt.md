# Support judgment

Adapted from FActScore (Min et al., EMNLP 2023): each atomic claim is labelled *supported* or
*not supported* by the knowledge source. The knowledge source here is the repository at a
pinned commit, which the judge reads directly.

## Instructions given to the judge

You are checking claims about the codebase at `{repo}` (pinned at commit `{commit}`). You do
not know which document each claim came from, and you must not try to find out.

For each line of `{batch}` (`{"key": ..., "claim": ...}`), one claim at a time:

1. Search the repository for the code the claim is about (grep, then read the file around the
   match). Do this for every claim; do not decide from memory or from general knowledge of the
   project.
2. Decide:
   - **supported**: the code at this commit shows the claim is true, including any specific
     names, defaults, orders or file locations it states.
   - **unsupported**: the code contradicts the claim, or a specific detail it states cannot be
     found in the code (a function, attribute, default or behaviour that does not exist).
3. Record the evidence you relied on: `evidence` is `path:line` (one line number, repo-relative
   path with forward slashes) and `quote` is a short exact substring copied from that line. For
   an unsupported claim, cite the line that contradicts it, or the closest line you checked.

Be strict about specifics: a claim with a wrong name, default or file is unsupported even if its
general idea is right. Do not modify the repository.

Write JSON Lines to `{output}`, one object per claim:
`{"key": "...", "verdict": "supported" | "unsupported", "evidence": "path:line", "quote": "...", "note": "..."}`
using a Python script with `json.dumps`.

## How the evidence is checked

`run.py score` opens every `evidence` location and checks that `quote` appears on that line (or
within two lines of it), the same anchor check `verify.py` applies to guides. A verdict whose
evidence does not check out is not counted, and the claim is judged again.
