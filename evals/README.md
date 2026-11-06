# Evaluating Onramp

Three evaluations, each built on an established method, each measuring something a reader of a
guide actually cares about:

| Question | Method | Where |
|---|---|---|
| Does the checker catch made-up or broken citations? | Fault injection (mutation testing) | [`fault_injection.py`](fault_injection.py) |
| Are the guide's statements about the code true? | FActScore (Min et al., EMNLP 2023) | [`factscore/`](factscore/) |
| Does reading the guide help someone answer real questions about the code? | SWE-QA (ACL Findings 2026) | [`swe_qa/`](swe_qa/) |

Every prompt, every model answer and every grade is committed here, so each number can be
checked line by line.

<!-- RESULTS:START -->
Results are added when the runs complete.
<!-- RESULTS:END -->

## 1. Fault injection: does the checker work?

[Mutation testing](https://en.wikipedia.org/wiki/Mutation_testing) plants known faults and counts
how many the tests catch. Here the "test" is `verify.py` and the faults are broken citations,
planted one at a time into copies of guides that already pass:

| Fault | What is changed | Correct behaviour |
|---|---|---|
| Fabricated anchor | the quoted code text is altered so it appears nowhere in the file (`def place_order(` becomes `def place_order_v2(`) | reject |
| Missing file | the path points at a file that does not exist | reject |
| Drifted lines | the line range moves 3 to 9 lines while the quoted text stays real | re-anchor to the original lines |
| Control | nothing is changed | accept (anything else is a false alarm) |

Run it on any verified guide:

```bash
python evals/fault_injection.py /path/to/repo [/another/repo ...] --per-kind 100 --seed 7
```

**What it does not show.** Passing these checks means every citation points at real code that
contains the quoted text. It does not prove the sentence around the citation is true. That is
what the next evaluation measures.

## 2. FActScore: are the statements true?

[FActScore](https://arxiv.org/abs/2305.14251) splits a long generated text into atomic facts and
reports the share supported by a knowledge source. The knowledge source here is the repository
at a pinned commit, read directly by the judge.

**Setup.** Flask at commit `85c5d93` (the commit SWE-QA pins). Two documents written by the same
model (Claude Opus 5.5) from the same checkout:

- **Onramp**: the guide from running the skill (`GUIDE.md`).
- **Baseline**: the same model asked, without the skill, to "read the codebase and write a
  thorough guide that helps a developer who has never seen it understand it".

**Protocol.**

1. Extract atomic claims from each document with the same prompt
   ([`extract_prompt.md`](factscore/extract_prompt.md)); the extractor sees only the document.
2. Sample the same number of claims from each, with a fixed seed, and shuffle them together so
   the judge cannot tell which document a claim came from (`run.py sample`).
3. A judge model with read access to the repository labels each claim supported or unsupported
   ([`judge_prompt.md`](factscore/judge_prompt.md)). Every verdict must cite a `path:line` and a
   quote copied from that line; batches are 30 claims, so each one gets its own search.
4. Unblind and score (`run.py score --repo <repo>`). The scorer opens every cited line and throws
   away any verdict whose quote is not there, so a judge cannot pass claims without checking them.

Two early judge passes did not meet this bar (one gave 59 of 60 claims a placeholder instead of a
line; the other did not record quotes and briefly saw the Onramp guide while searching). They are
kept, unused, in [`factscore/runs/flask/discarded/`](factscore/runs/flask/discarded/) with the
reasons.

## 3. SWE-QA: does the guide transfer understanding?

[SWE-QA](https://arxiv.org/abs/2509.14635) is a benchmark of questions developers actually ask
about real repositories, with reference answers written against the code. Its Flask set has 48
questions (Apache-2.0, from [SWE-QA-Bench](https://github.com/peng-weihan/SWE-QA-Bench)).

**Setup.** A smaller model (Claude Haiku 5.5) answers all 48 questions four times, each time
allowed to read exactly one thing:

| Condition | What the answering model may read |
|---|---|
| `closed` | nothing (its own prior knowledge of Flask) |
| `readme` | Flask's `README.md` |
| `explainer` | the baseline document from section 2 |
| `onramp` | Onramp's `GUIDE.md` |

It may not open the repository, search, or browse. Flask is famous, so `closed` is a strong
baseline: the model already knows a lot about it.

**Grading.** SWE-QA's official judge prompt ([`judge_prompt.txt`](swe_qa/judge_prompt.txt), used
verbatim) scores each answer against the reference on five dimensions (correctness,
completeness, relevance, clarity, reasoning), 1 to 20 each, 100 in total. All 192 answers are
shuffled together and graded blind by Claude Sonnet 5.5 (`run.py blind`, then `run.py score`,
which also reports 95% bootstrap confidence intervals and head-to-head wins).

## Limitations

- One repository (Flask) for the model-graded evaluations. Flask is well known, which makes the
  baselines strong and the comparison conservative, but it is still one codebase.
- Answers and grades come from Claude models. The judge is blind to the condition, but a
  different judge family could score differently.
- The Onramp guide is longer than the baseline document. That is part of what the skill does,
  and the SWE-QA scores show whether the extra length turns into understanding.
- FActScore measures precision (are the stated facts right), not coverage.
