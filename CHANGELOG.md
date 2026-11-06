# Changelog

All notable changes to Onramp are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses
[Semantic Versioning](https://semver.org/).

## [1.0.1] - 2026-11-06

### Fixed

- `scan.py` skips installed agent skills (`.claude/skills/`, `.agents/skills/` and similar), so a
  project-level install of Onramp or any other skill is not counted as the project's own code.

## [1.0.0] - 2026-11-06

First public release.

### Added

- **The skill** (`skills/onramp/SKILL.md`): full guide, `quick`, `explain`, `trace`, `update` and
  `tutor` modes, written for any agent that reads `SKILL.md` and runs Python.
- **`scan.py`**: inventory, manifests, entry points, import graph for JS/TS, Python, Go, Rust,
  Java/Kotlin, C/C++, Ruby and PHP, importance ranking, git history, env vars, TODOs, deleted
  files and Claude Code session detection.
- **`sessions.py`**: opt-in digest of local Claude Code transcripts with secret redaction.
- **`verify.py`**: checks every `[[path:lines|anchor]]` citation against the code, re-anchors
  drifted lines, rejects unsupported claims, merges and repairs work fragments, checks single
  fragments for subagents.
- **`render.py`**: one self-contained HTML guide with the real code embedded, plus `GUIDE.md`.
- **Viewer**: route planner for 1 hour to 1 week and four goals, the road map with progress,
  lessons with checkpoints, hands-on stops on longer routes, code panel, file explorer, computed
  dependency map, search, light and dark themes.
- **Evals**: fault injection for the verifier, FActScore-style grounding and SWE-QA
  comprehension, with every prompt, answer and grade in `evals/`.
- **Website** with live PaperMind and nanoGPT demos, deployed on Vercel.

[1.0.0]: https://github.com/SanyamWadhwa07/onramp/releases/tag/v1.0.0
[1.0.1]: https://github.com/SanyamWadhwa07/onramp/releases/tag/v1.0.1
