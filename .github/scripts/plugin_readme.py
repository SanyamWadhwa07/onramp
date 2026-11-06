"""Prints README.md with every relative link made absolute, for the `plugin` branch.

The plugin branch holds only what the plugin installs (the manifest, skills/onramp, README,
LICENSE, CHANGELOG, SECURITY), so links into docs/, evals/ or CONTRIBUTING.md would break there.
Files under docs/ are served by the website; everything else points at the release on GitHub.

Usage: python plugin_readme.py README.md <git ref>
"""
import re
import sys

REPO = "https://github.com/SanyamWadhwa07/onramp"
SITE = "https://onramp-skill.vercel.app"


def absolute(path, ref, image):
    if re.match(r"[a-z][a-z0-9+.-]*:|#|/", path):  # already absolute, an anchor, or site-rooted
        return path
    if path.startswith("docs/"):
        return SITE + "/" + path[len("docs/"):]
    if image:
        return "%s/raw/%s/%s" % (REPO, ref, path)
    return "%s/%s/%s/%s" % (REPO, "tree" if path.endswith("/") else "blob", ref, path)


def rewrite(text, ref):
    text = re.sub(r"(!?)\[([^\]]*)\]\(([^)\s]+)",
                  lambda m: "%s[%s](%s" % (m.group(1), m.group(2), absolute(m.group(3), ref, bool(m.group(1)))), text)
    return re.sub(r'\b(src|href)="([^"]+)"',
                  lambda m: '%s="%s"' % (m.group(1), absolute(m.group(2), ref, m.group(1) == "src")), text)


if __name__ == "__main__":
    with open(sys.argv[1], encoding="utf-8") as fh:
        sys.stdout.buffer.write(rewrite(fh.read(), sys.argv[2]).encode("utf-8"))
