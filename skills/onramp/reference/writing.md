# Writing the guide

The reader opened this project and felt lost. Every sentence should make them less lost.

## Teach in this order

1. **The point first.** Each lesson opens with what the reader will understand by the end.
   The `summary` alone should be worth reading.
2. **Plain words, then the term.** "The app keeps a short list of recent results in memory so it
   doesn't redo work. That list is a cache." Never the reverse.
3. **Concrete before abstract.** Show the real function, the real request, the real row in the
   table, then name the pattern.
4. **One idea per lesson.** If a lesson needs two headings, it is two lessons.
5. **Follow the data.** Flows trace one real action from the user's click to the database and
   back, naming each function on the way.
6. **Say why.** After "what it does", say why it exists or why it is done this way. If the code
   or history does not say, write "probably" and mark the decision `inferred`.

## Voice

- Second person, present tense, active voice: "You start the server with…", "`router.py` sends…".
- Short sentences. One clause where one clause will do.
- Explain every acronym and library the first time. Assume a smart reader who has not seen
  this stack before; `for: ["new"]` primers carry the basics so other lessons can move faster.
- Numbers from the code, not adjectives: "retries 3 times with a 2-second backoff", not
  "retries robustly".
- No filler: avoid "robust", "seamless", "leverages", "powerful", "comprehensive",
  "cutting-edge", "it's worth noting", "in summary". No marketing tone; this is a field guide.
- Be honest about the code. If something is fragile, unused, duplicated or confusing, say so
  plainly in `care` and point at it. Do not invent problems either.

## Analogies

One per big idea, from everyday life, and say where it stops working.
"The message bus is like a group chat for agents: anyone can post, and agents only read the
topics they follow. Unlike a chat, messages here are gone once read."

## Citations as evidence

- A technical claim without a citation is a guess. Cite the lines that prove it.
- Prefer citing the definition (the function, class, route, config key) over a usage.
- Quote code sparingly in prose (an identifier in backticks); the viewer shows the real code
  when the reader clicks the citation.

## Checkpoints

Test understanding, not recall of trivia. Good: "A user's upload fails after the PDF is saved.
Which module do you open first?" Bad: "How many lines is main.py?" Three or four choices, one
clearly right, wrong ones plausible. The `explain` says why, with a citation.

## Exercises

Real changes a newcomer could make in this codebase: add a field, add a route, change a
threshold and observe it, write a missing test. Each one names the files to touch and how to
know it worked.

## Markdown the viewer renders

Paragraphs, `###` and `####` headings, bullet and numbered lists (one level), fenced code blocks,
`>` notes, pipe tables, **bold**, *italics*, `inline code`, `https://` links and citations. Nothing
else: no images, no HTML, no nested lists.

## Lengths

| Item | Length |
|---|---|
| `summary` | 1–2 sentences |
| lesson `body` | 120–350 words |
| `deeper` | up to 300 words |
| file card `summary` | 2–5 sentences |
| flow step `explain` | 1–3 sentences |
