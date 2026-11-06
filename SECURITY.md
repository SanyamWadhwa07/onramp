# Security policy

## What Onramp touches

Onramp runs inside your own coding agent's session. Its scripts:

- read files in the repository you point them at, and its git history
- read Claude Code transcripts for that repository **only** if you agree when asked
- write only inside `<repo>/.onramp/`
- make no network calls

A generated guide is a single local HTML file. When opened, it loads fonts, the diagram renderer
and syntax highlighting from public CDNs (Google Fonts, jsDelivr, cdnjs). It sends nothing about
your code anywhere.

Things to keep in mind:

- A guide embeds real excerpts of your code. Treat it like the code itself before sharing it,
  and render with `--public` to drop local paths.
- `sessions.py` redacts text that looks like an API key or token, but review any guide built
  with session history before publishing it.

## Supported versions

The latest release receives security fixes.

## Reporting a vulnerability

Please do not open a public issue. Report it privately through
[GitHub security advisories](https://github.com/SanyamWadhwa07/onramp/security/advisories/new).
You will get an acknowledgement within three days and a fix or a plan within two weeks.
