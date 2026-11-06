# Support judgment

Adapted from FActScore (Min et al., EMNLP 2023): each atomic claim is labelled *supported* or
*not supported* by the knowledge source. The knowledge source here is the repository at a
pinned commit, which the judge reads directly.

## Instructions given to the judge

You are checking claims about the codebase at `{repo}` (pinned at commit `{commit}`). You do
not know which document each claim came from, and you must not try to find out.

For each line of `{batch}` (`{"key": ..., "claim": ...}`):

1. Search the repository for the code the claim is about (grep, read the files).
2. Decide:
   - **supported**: the code at this commit shows the claim is true, including any specific
     names, defaults, orders or file locations it states.
   - **unsupported**: the code contradicts the claim, or the specific detail it states cannot
     be found in the code (a function, attribute, default or behaviour that does not exist).
3. Record one short piece of evidence: the `path:line` you relied on.

Be strict about specifics: a claim with a wrong name, default or file is unsupported even if its
general idea is right. Do not guess from general knowledge of the project; only the code at this
commit counts. Do not modify the repository.

Write JSON Lines to `{output}`, one object per claim:
`{"key": "...", "verdict": "supported" | "unsupported", "evidence": "path:line", "note": "..."}`
using a Python script with `json.dumps`.
