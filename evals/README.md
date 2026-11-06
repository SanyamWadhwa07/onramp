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
## Results

### 1. Fault injection: the checker catches every planted fault

Run on the PaperMind and nanoGPT guides (seed 7, 100 citations sampled from each):

| Fault | Handled correctly |
|---|---|
| Fabricated anchor rejected | **200 / 200** |
| Missing file rejected | **200 / 200** |
| Drifted lines re-anchored to the right place | **125 / 125** |
| Real citation accepted (no false alarm) | **200 / 200** |

Raw cases: [`results/fault_injection.json`](results/fault_injection.json).

### 2. FActScore: the guide's statements hold up against the code

Flask at `85c5d93`, 60 claims sampled from each document, judged blind against the source,
every verdict backed by a quote the scorer verified:

| Document | Claims extracted | Claims judged | Supported by the code | FActScore |
|---|---|---|---|---|
| Baseline (plain "explain this codebase") | 811 | 60 | 60 | **100.0%** |
| Onramp guide | 717 | 60 | 58 | **96.7%** |

Both documents are highly accurate; the difference is two claims and within sampling noise.
Onramp's two unsupported claims were real, small errors: an "only" that had exceptions (the
built-in `routes` and `shell` commands also load the app) and a call attributed to `app.py`
that happens in `ctx.py`. Both sentences cited genuine code; the prose around the citation
overstated it. `reference/writing.md` now tells the agent to watch for exactly these.

Verdicts and evidence: [`factscore/runs/flask/`](factscore/runs/flask/).

### 3. SWE-QA: on Flask, the guide matches what the model already knows

48 questions, 192 answers graded blind with the official SWE-QA rubric (100 points):

| Condition | Score | 95% CI | Correctness | Completeness |
|---|---|---|---|---|
| `closed` (no context) | **67.2** | 63.7 to 70.5 | 12.8 | 10.8 |
| `onramp` (the guide) | **67.1** | 64.0 to 70.0 | 13.0 | 10.9 |
| `explainer` (baseline document) | **64.5** | 61.0 to 67.9 | 12.3 | 10.4 |
| `readme` (Flask's README) | **63.6** | 59.4 to 67.5 | 11.7 | 10.0 |

Head to head, the Onramp-guided answers won 28 of 48 questions against the baseline document
(2 ties, 18 losses) and 23 against the README (7 ties, 18 losses).

**How to read this.** Flask is in the answering model's training data, so the closed-book
baseline already knows most answers; reading the README or the baseline document *lowered* the
score slightly, and reading the Onramp guide kept it level. The confidence intervals overlap, so
on Flask the guide does not measurably beat the model's own knowledge. This benchmark cannot
show the case Onramp is built for, code the model has never seen, because the model would have
nothing to fall back on there. We report the result as it came out.

Answers, blinding key and grades: [`swe_qa/runs/flask/`](swe_qa/runs/flask/).

### What the results say

- The verifier does its job: no planted fault got through, and it raised no false alarms.
- The guides are accurate (96.7% of sampled claims supported), on par with a strong baseline
  written by the same model.
- On a famous codebase, the guide carries as much answerable knowledge as the model's memory and
  more than the README or a plain explainer. Onramp's other strengths, the route, the order, the
  checkpoints, the code beside every claim, are about how a person learns and are not measured
  by these benchmarks.
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
