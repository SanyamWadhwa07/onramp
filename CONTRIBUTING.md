# Contributing to Onramp

Thanks for helping. Onramp is small on purpose, so most contributions are a few lines in one of
four scripts, the viewer, or the instructions the agent follows.

## Ground rules

- **Standard library only.** The scripts run on Python 3.8+ with nothing to install. Please keep it
  that way.
- **No build step.** The viewer is plain HTML, CSS and JavaScript, inlined by `render.py`.
- **Every claim is grounded.** Changes to `SKILL.md` or the reference docs should make guides more
  accurate or easier to learn from, never less checkable.
- **Local by default.** Nothing the skill produces may send data anywhere. Analytics exist only on
  the website in `docs/`, never in generated guides.

## Layout

```
skills/onramp/SKILL.md        what the agent does, step by step
skills/onramp/reference/      guide.json contract, writing rules, subagent brief
skills/onramp/scripts/        scan.py, sessions.py, verify.py, render.py (+ _common.py)
skills/onramp/assets/         the guide viewer
tests/                        unit tests and the tinyshop fixture
evals/                        fault injection, FActScore and SWE-QA evaluations
docs/                         the website and live demos (deployed on Vercel)
```

## Set up and test

```bash
git clone https://github.com/SanyamWadhwa07/onramp
cd onramp
python -m unittest discover -s tests -v
python evals/fault_injection.py tests/fixtures/tinyshop   # needs a verified guide; see evals/README.md
```

To try a change on a real project, point your agent at your working copy instead of the
installed skill, or run the scripts directly:

```bash
python skills/onramp/scripts/scan.py /path/to/repo
python skills/onramp/scripts/verify.py /path/to/repo --merge --fix
python skills/onramp/scripts/render.py /path/to/repo --open
```

To work on the viewer, render any guide and open `.onramp/index.html`; edit
`skills/onramp/assets/` and render again.

## Pull requests

1. Open an issue first for anything bigger than a fix, so we can agree on the approach.
2. Keep the change focused. One concern per pull request.
3. Add or update tests in `tests/` for script changes.
4. Run the test suite. CI runs it on Linux, macOS and Windows, from Python 3.8 to 3.13.
5. Write commit messages in the [Conventional Commits](https://www.conventionalcommits.org/)
   style: `fix(verify): keep concepts when merging fragments`.

## Releases

Maintainers tag `vX.Y.Z` on `main`. The release workflow runs the tests, packages
`skills/onramp` as `onramp-skill.zip` and publishes it on GitHub Releases. Update
`CHANGELOG.md` and the version in `SKILL.md` and `.claude-plugin/plugin.json` first.

## Code of conduct

This project follows the [Contributor Covenant](CODE_OF_CONDUCT.md). By taking part you agree to
uphold it.
