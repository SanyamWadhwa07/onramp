# Atomic claim extraction

Adapted from FActScore (Min et al., EMNLP 2023), where a long generation is broken into atomic
facts before each one is checked against a knowledge source. Here the knowledge source is the
repository the document describes.

## Instructions given to the extractor

Read the whole document at `{document}`. It describes the codebase at `{repo}`.

Break it into **atomic claims about the code**. An atomic claim:

- states exactly one checkable fact about the codebase: what a function, class, attribute,
  module, file, setting or command is or does; a default value; an order of calls; where
  something lives; how two parts interact
- stands alone: replace pronouns and "it" with the thing they refer to, and name the file,
  class or function when the document makes clear which one is meant
- keeps the document's meaning and specificity; do not add facts, soften claims or fix errors

Skip anything that is not a claim about this code: opinions, advice, analogies, learning
tips, statements about the document itself, and general facts about Python or the web that do
not depend on this repository. Drop link and citation syntax, keeping the claim it supports.

Extract every claim, in document order. Write them as JSON Lines to `{output}`, one object per
line, `{"claim": "...", "section": "<nearest heading>"}`, using a Python script with
`json.dumps` so the escaping is correct. Do not open any file other than the document.
