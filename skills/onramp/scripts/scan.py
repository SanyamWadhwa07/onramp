#!/usr/bin/env python3
"""Inventory a repository into .onramp/scan.json.

Deterministic facts only: files, languages, manifests, entry points, an import graph,
an importance ranking, git history, env vars, TODOs and Claude session presence.
The model reads this instead of guessing, and the viewer draws its maps from it.

usage: scan.py [repo] [--out PATH] [--quiet]
"""
import argparse
import datetime as dt
import hashlib
import json
import math
import os
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _common import (  # noqa: E402
    CODE_LANGS, DATA_EXT, LOCKFILES, VERSION, claude_project_dirs, is_binary_path, lang_of,
    list_files, onramp_dir, posix, read_text, run_git, save_json,
)

JS_EXT = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts", ".vue", ".svelte", ".astro")
JS_RES = [
    re.compile(r"""^\s*import\s+(?:type\s+)?(?:[\w*{}\s,$]+?\s+from\s+)?['"]([^'"\n]+)['"]""", re.M),
    re.compile(r"""^\s*export\s+(?:type\s+)?[\w*{}\s,$]+?\s+from\s+['"]([^'"\n]+)['"]""", re.M),
    re.compile(r"""\brequire\(\s*['"]([^'"\n]+)['"]\s*\)"""),
    re.compile(r"""\bimport\(\s*['"]([^'"\n]+)['"]\s*\)"""),
]
PY_IMPORT = re.compile(r"^[ \t]*import[ \t]+([\w.]+(?:[ \t]*,[ \t]*[\w.]+)*)", re.M)
PY_FROM = re.compile(r"^[ \t]*from[ \t]+(\.*[\w.]*)[ \t]+import[ \t]+(?:\(([^)]*)\)|([\w*][\w \t,*]*))", re.M)
GO_SINGLE = re.compile(r'^\s*import\s+(?:\w+\s+)?"([^"]+)"', re.M)
GO_BLOCK = re.compile(r"^\s*import\s*\((.*?)\)", re.M | re.S)
RS_MOD = re.compile(r"^\s*(?:pub(?:\([^)]*\))?\s+)?mod\s+(\w+)\s*;", re.M)
RS_USE = re.compile(r"^\s*(?:pub\s+)?use\s+(crate|super|self)((?:::\w+)+)", re.M)
JVM_IMPORT = re.compile(r"^\s*import\s+(?:static\s+)?([\w.]+)", re.M)
C_INCLUDE = re.compile(r'^\s*#\s*include\s+"([^"]+)"', re.M)
RB_REQ = re.compile(r"""^\s*require(_relative)?\s*\(?\s*['"]([^'"]+)['"]""", re.M)
PHP_REQ = re.compile(r"""\b(?:require|include)(?:_once)?\s*\(?\s*(?:__DIR__\s*\.\s*)?['"]([^'"]+\.php)['"]""")
PHP_USE = re.compile(r"^\s*use\s+([\w\\]+)", re.M)

ENV_RES = [
    re.compile(r"process\.env\.([A-Z][A-Z0-9_]{1,})"),
    re.compile(r"""process\.env\[\s*['"]([A-Z][A-Z0-9_]+)['"]"""),
    re.compile(r"import\.meta\.env\.([A-Z][A-Z0-9_]{1,})"),
    re.compile(r"""os\.environ(?:\.get)?\(\s*['"]([A-Z][A-Z0-9_]+)['"]"""),
    re.compile(r"""os\.environ\[\s*['"]([A-Z][A-Z0-9_]+)['"]"""),
    re.compile(r"""(?:os\.)?getenv\(\s*['"]([A-Z][A-Z0-9_]+)['"]"""),
    re.compile(r"""os\.Getenv\(\s*"([A-Z][A-Z0-9_]+)"\s*\)"""),
    re.compile(r"""env::var\(\s*"([A-Z][A-Z0-9_]+)"\s*\)"""),
    re.compile(r"""System\.getenv\(\s*"([A-Z][A-Z0-9_]+)"\s*\)"""),
    re.compile(r"""ENV\[\s*['"]([A-Z][A-Z0-9_]+)['"]\s*\]"""),
]
ENV_FILE_LINE = re.compile(r"^\s*(?:export\s+)?([A-Z][A-Z0-9_]+)\s*=", re.M)
TODO_RE = re.compile(r"(?:#|//|/\*|<!--|--|\*)\s*\b(TODO|FIXME|HACK|XXX)\b[:\s(]*(.{0,140})")

TEST_PATH = re.compile(
    r"(^|/)(tests?|__tests__|spec|specs|e2e|testing)(/|$)|(^|/)test_[^/]+\.py$|_test\.(go|py|rb|exs?)$"
    r"|\.(test|spec)\.[jt]sx?$|Tests?\.(java|kt|cs|swift)$"
)
CONFIG_NAMES = re.compile(
    r"(^|/)(Dockerfile[^/]*|docker-compose[^/]*\.ya?ml|compose\.ya?ml|Makefile|Procfile|Justfile|"
    r"\.env[^/]*|[^/]*\.config\.[cm]?[jt]s|[^/]*rc(\.json|\.js|\.cjs|\.ya?ml)?|tsconfig[^/]*\.json|"
    r"package\.json|pyproject\.toml|setup\.(py|cfg)|requirements[^/]*\.txt|go\.mod|Cargo\.toml|"
    r"pom\.xml|build\.gradle(\.kts)?|Gemfile|composer\.json|[^/]*\.ya?ml|[^/]*\.toml|[^/]*\.ini)$"
)
DOC_EXT = {".md", ".mdx", ".rst", ".txt", ".adoc"}
GROUP_DIRS = {"src", "lib", "app", "apps", "packages", "services", "backend", "frontend", "server",
              "client", "internal", "pkg", "cmd", "modules", "libs", "crates", "web", "api"}


def kind_of(path, lang):
    name = os.path.basename(path)
    ext = os.path.splitext(name)[1].lower()
    if name in LOCKFILES:
        return "lock"
    if is_binary_path(path):
        return "data" if ext in DATA_EXT else "asset"
    if ext in DATA_EXT:
        return "data"
    if TEST_PATH.search(path):
        return "test"
    if CONFIG_NAMES.search(path) or lang in ("JSON", "YAML", "TOML", "INI", "XML"):
        return "config"
    if ext in DOC_EXT:
        return "doc"
    if lang in CODE_LANGS:
        return "source"
    return "other"


def strip_json_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"(^|[^:\"'])//[^\n]*", r"\1", text)
    return re.sub(r",(\s*[}\]])", r"\1", text)


def load_loose_json(text):
    try:
        return json.loads(text)
    except ValueError:
        try:
            return json.loads(strip_json_comments(text))
        except ValueError:
            return None


class Resolver:
    """Turns import strings into repo files. Best effort; never raises."""

    def __init__(self, root, files, texts):
        self.root = root
        self.files = set(files)
        self.suffix = defaultdict(list)  # 'a/b/c' (no ext) -> [paths]
        for f in files:
            stem = os.path.splitext(f)[0]
            parts = stem.split("/")
            for i in range(len(parts)):
                self.suffix["/".join(parts[i:])].append(f)
        self.tsconfigs = self._load_tsconfigs(files, texts)
        self.go_module = None
        for f in files:
            if os.path.basename(f) == "go.mod" and texts.get(f):
                m = re.search(r"^module\s+(\S+)", texts[f], re.M)
                if m:
                    self.go_module = (posix(os.path.dirname(f)), m.group(1))
                    break
        self.go_dirs = defaultdict(list)
        for f in files:
            if f.endswith(".go") and not f.endswith("_test.go"):
                self.go_dirs[posix(os.path.dirname(f))].append(f)

    def _load_tsconfigs(self, files, texts):
        out = []
        for f in files:
            if os.path.basename(f) in ("tsconfig.json", "jsconfig.json") and texts.get(f):
                data = load_loose_json(texts[f]) or {}
                opts = data.get("compilerOptions") or {}
                base_dir = posix(os.path.dirname(f))
                base_url = posix(os.path.normpath(os.path.join(base_dir, opts.get("baseUrl", "."))))
                if base_url == ".":
                    base_url = ""
                paths = opts.get("paths") or {}
                out.append((base_dir, base_url, paths))
        out.sort(key=lambda t: -len(t[0]))
        return out

    def _try_js(self, base):
        base = posix(os.path.normpath(base)).lstrip("./") if base not in ("", ".") else ""
        if base.startswith("../"):
            return None
        cands = [base] + [base + e for e in JS_EXT + (".d.ts", ".json", ".css", ".scss")]
        cands += [base + "/index" + e for e in JS_EXT]
        for c in cands:
            if c in self.files:
                return c
        return None

    def js(self, src, spec):
        if spec.startswith("."):
            return self._try_js(os.path.join(os.path.dirname(src), spec)), None
        for base_dir, base_url, paths in self.tsconfigs:
            if base_dir and not src.startswith(base_dir + "/"):
                continue
            for pattern, targets in paths.items():
                prefix = pattern.rstrip("*")
                if (pattern.endswith("*") and spec.startswith(prefix)) or spec == pattern:
                    rest = spec[len(prefix):] if pattern.endswith("*") else ""
                    for t in targets:
                        hit = self._try_js(os.path.join(base_url, t.replace("*", rest)))
                        if hit:
                            return hit, None
            if base_url:
                hit = self._try_js(os.path.join(base_url, spec))
                if hit:
                    return hit, None
        if spec.startswith(("@/", "~/")):
            for root in ("src/", "", "app/"):
                hit = self._try_js(root + spec[2:])
                if hit:
                    return hit, None
        if spec.startswith(("http:", "https:", "data:", "node:")):
            return None, spec.split(":", 1)[0] if spec.startswith("node:") else None
        parts = spec.split("/")
        pkg = "/".join(parts[:2]) if spec.startswith("@") else parts[0]
        return None, pkg

    def _by_suffix(self, dotted, src, exts):
        key = dotted.replace(".", "/")
        best = []
        for cand in self.suffix.get(key, []) + self.suffix.get(key + "/__init__", []):
            if os.path.splitext(cand)[1] in exts:
                best.append(cand)
        if not best:
            return None
        top = src.split("/")[0]
        best.sort(key=lambda p: (p.split("/")[0] != top, len(p)))
        return best[0]

    def python(self, src, module, names):
        out = []
        if module.startswith("."):
            dots = len(module) - len(module.lstrip("."))
            base = os.path.dirname(src)
            for _ in range(dots - 1):
                base = os.path.dirname(base)
            rest = module.lstrip(".").replace(".", "/")
            pkg = posix(os.path.join(base, rest)) if rest else posix(base)
            found = False
            for n in names:
                for c in (pkg + "/" + n + ".py", pkg + "/" + n + "/__init__.py"):
                    if c.lstrip("/") in self.files:
                        out.append(c.lstrip("/"))
                        found = True
            if not found:
                for c in (pkg + ".py", pkg + "/__init__.py"):
                    if c.lstrip("/") in self.files:
                        out.append(c.lstrip("/"))
            return out, None
        for n in names:
            hit = self._by_suffix(module + "." + n, src, (".py",))
            if hit:
                out.append(hit)
        if not out:
            hit = self._by_suffix(module, src, (".py",))
            if hit:
                out.append(hit)
        return out, (None if out else module.split(".")[0])

    def go(self, spec):
        if self.go_module:
            mod_dir, mod = self.go_module
            if spec == mod or spec.startswith(mod + "/"):
                rel = spec[len(mod):].lstrip("/")
                d = posix(os.path.join(mod_dir, rel)) if mod_dir else rel
                return self.go_dirs.get(d.strip("/"), []), None
        return [], spec.split("/")[0] if "." not in spec.split("/")[0] else "/".join(spec.split("/")[:3])

    def rust_mod(self, src, name):
        d = os.path.dirname(src)
        stem = os.path.splitext(os.path.basename(src))[0]
        if stem not in ("main", "lib", "mod"):
            d = os.path.join(d, stem)
        for c in (os.path.join(d, name + ".rs"), os.path.join(d, name, "mod.rs")):
            c = posix(c)
            if c in self.files:
                return c
        return None

    def rust_use(self, src, head, path):
        segs = [s for s in path.split("::") if s]
        if head == "crate":
            parts = src.split("/")
            base = "/".join(parts[: parts.index("src") + 1]) if "src" in parts else ""
        else:
            base = os.path.dirname(src)
        for i in range(len(segs), 0, -1):
            cand = posix(os.path.join(base, *segs[:i]))
            for c in (cand + ".rs", cand + "/mod.rs"):
                if c in self.files:
                    return c
        return None

    def jvm(self, src, dotted):
        return self._by_suffix(dotted, src, (".java", ".kt", ".kts", ".scala"))

    def c_include(self, src, inc):
        c = posix(os.path.normpath(os.path.join(os.path.dirname(src), inc)))
        if c in self.files:
            return c
        stem = os.path.splitext(inc)[0]
        for cand in self.suffix.get(posix(stem), []):
            if cand.endswith(inc):
                return cand
        return None

    def ruby(self, src, relative, spec):
        if relative:
            c = posix(os.path.normpath(os.path.join(os.path.dirname(src), spec)))
        else:
            c = "lib/" + spec
        for cand in (c, c + ".rb"):
            if cand in self.files:
                return cand
        return None

    def php(self, src, spec, use=False):
        if use:
            return self._by_suffix(spec.replace("\\", "."), src, (".php",))
        c = posix(os.path.normpath(os.path.join(os.path.dirname(src), spec.lstrip("/"))))
        return c if c in self.files else None


def extract_imports(path, text, res):
    """Return (internal paths, external package names)."""
    internal, external = [], []
    ext = os.path.splitext(path)[1].lower()

    def add(hit, ext_name=None):
        if isinstance(hit, list):
            internal.extend(hit)
        elif hit:
            internal.append(hit)
        if ext_name:
            external.append(ext_name)

    if ext in JS_EXT:
        for rx in JS_RES:
            for spec in rx.findall(text):
                hit, pkg = res.js(path, spec)
                add(hit, pkg)
    elif ext == ".py":
        for m in PY_IMPORT.finditer(text):
            for mod in m.group(1).split(","):
                hits, pkg = res.python(path, mod.strip(), [])
                add(hits, pkg)
        for m in PY_FROM.finditer(text):
            names = [n.strip() for n in (m.group(2) or m.group(3) or "").split(",") if n.strip()]
            names = [n.split()[0] for n in names if n.split()]
            hits, pkg = res.python(path, m.group(1), [n for n in names if n != "*"])
            add(hits, pkg)
    elif ext == ".go":
        specs = GO_SINGLE.findall(text)
        for block in GO_BLOCK.findall(text):
            specs += re.findall(r'"([^"]+)"', block)
        for spec in specs:
            hits, pkg = res.go(spec)
            add(hits, pkg if not hits else None)
    elif ext == ".rs":
        for name in RS_MOD.findall(text):
            add(res.rust_mod(path, name))
        for head, rest in RS_USE.findall(text):
            add(res.rust_use(path, head, rest))
    elif ext in (".java", ".kt", ".kts", ".scala"):
        for dotted in JVM_IMPORT.findall(text):
            hit = res.jvm(path, dotted)
            add(hit, None if hit else ".".join(dotted.split(".")[:2]))
    elif ext in (".c", ".h", ".cc", ".cpp", ".cxx", ".hpp", ".hh", ".m", ".mm"):
        for inc in C_INCLUDE.findall(text):
            add(res.c_include(path, inc))
    elif ext == ".rb":
        for rel, spec in RB_REQ.findall(text):
            hit = res.ruby(path, bool(rel), spec)
            add(hit, None if hit or rel else spec.split("/")[0])
    elif ext == ".php":
        for spec in PHP_REQ.findall(text):
            add(res.php(path, spec))
        for spec in PHP_USE.findall(text):
            add(res.php(path, spec, use=True))
    internal = sorted({p for p in internal if p and p != path})
    external = sorted({e for e in external if e and not e.startswith(".")})
    return internal, external


def module_of(path):
    parts = path.split("/")
    if len(parts) == 1:
        return "(root)"
    if parts[0] in GROUP_DIRS and len(parts) > 2:
        return parts[0] + "/" + parts[1]
    return parts[0]


def parse_manifests(files, texts):
    out = []
    for f in files:
        name = os.path.basename(f)
        text = texts.get(f)
        if not text:
            continue
        m = {"path": f}
        if name == "package.json":
            data = load_loose_json(text) or {}
            m.update(type="npm", name=data.get("name"), scripts=data.get("scripts") or {},
                     deps=sorted((data.get("dependencies") or {}).keys()),
                     dev_deps=sorted((data.get("devDependencies") or {}).keys()),
                     main=data.get("main"), bin=data.get("bin"))
        elif name == "pyproject.toml":
            deps = re.findall(r'^\s*"([A-Za-z0-9_.\-\[\]]+)', text.split("dependencies", 1)[1], re.M) \
                if "dependencies" in text else []
            scripts = dict(re.findall(r'^\s*([\w\-]+)\s*=\s*"([\w.:]+)"', text.split("[project.scripts]", 1)[1].split("\n[", 1)[0], re.M)) \
                if "[project.scripts]" in text else {}
            nm = re.search(r'^\s*name\s*=\s*"([^"]+)"', text, re.M)
            m.update(type="python", name=nm.group(1) if nm else None,
                     deps=sorted({re.split(r"[<>=!~\[;\s]", d)[0] for d in deps})[:80], scripts=scripts)
        elif re.match(r"requirements.*\.txt$", name):
            deps = [re.split(r"[<>=!~\[;\s]", line.strip())[0] for line in text.splitlines()
                    if line.strip() and not line.strip().startswith(("#", "-"))]
            m.update(type="python", deps=sorted(set(d for d in deps if d)))
        elif name == "go.mod":
            mod = re.search(r"^module\s+(\S+)", text, re.M)
            deps = re.findall(r"^\s*([\w.\-/]+\.[\w.\-/]+)\s+v[\d.]", text, re.M)
            m.update(type="go", name=mod.group(1) if mod else None, deps=sorted(set(deps)))
        elif name == "Cargo.toml":
            nm = re.search(r'^\s*name\s*=\s*"([^"]+)"', text, re.M)
            dep_block = re.findall(r"\[(?:dev-)?dependencies\]\n(.*?)(?:\n\[|\Z)", text, re.S)
            deps = re.findall(r"^\s*([\w\-]+)\s*=", "\n".join(dep_block), re.M)
            m.update(type="cargo", name=nm.group(1) if nm else None, deps=sorted(set(deps)))
        elif name in ("pom.xml", "build.gradle", "build.gradle.kts"):
            deps = re.findall(r"<artifactId>([^<]+)</artifactId>", text) or \
                re.findall(r"""['"]([\w.\-]+:[\w.\-]+)(?::[\w.\-]+)?['"]""", text)
            m.update(type="jvm", deps=sorted(set(deps))[:80])
        elif name in ("Gemfile", "composer.json", "pubspec.yaml", "mix.exs"):
            m.update(type=name)
        elif name in ("Makefile", "Justfile"):
            targets = re.findall(r"^([A-Za-z][\w\-]*):(?!=)", text, re.M)
            m.update(type="make", scripts={t: "" for t in targets[:40]})
        elif re.match(r"(docker-)?compose.*\.ya?ml$", name):
            services = re.findall(r"^  ([\w\-]+):\s*$", text.split("services:", 1)[1], re.M) \
                if "services:" in text else []
            m.update(type="compose", services=services[:30])
        elif name.startswith("Dockerfile"):
            cmd = re.findall(r"^(?:CMD|ENTRYPOINT)\s+(.+)$", text, re.M)
            base = re.findall(r"^FROM\s+(?:--\S+\s+)?(\S+)", text, re.M)
            m.update(type="docker", base=base, cmd=cmd[-1] if cmd else None)
        else:
            continue
        out.append(m)
    return out


def find_entrypoints(files, texts, manifests):
    eps = {}

    def add(path, why):
        if path in texts or path in files_set:
            eps.setdefault(path, why)

    files_set = set(files)
    for m in manifests:
        d = os.path.dirname(m["path"])
        if m.get("type") == "npm":
            for key in ("main",):
                if m.get(key):
                    add(posix(os.path.normpath(os.path.join(d, m[key]))), "package.json main")
            for script, cmd in (m.get("scripts") or {}).items():
                for tok in re.findall(r"[\w./\-]+\.(?:[cm]?[jt]sx?|py)", cmd or ""):
                    add(posix(os.path.normpath(os.path.join(d, tok))), "npm script '%s'" % script)
        if m.get("type") == "python":
            for target in (m.get("scripts") or {}).values():
                mod = target.split(":")[0].replace(".", "/")
                for c in files:
                    if c.endswith(mod + ".py"):
                        add(c, "pyproject script")
    patterns = [
        (re.compile(r"""if\s+__name__\s*==\s*['"]__main__['"]"""), "runs as a script (__main__)"),
        (re.compile(r"\bFastAPI\s*\("), "creates the FastAPI app"),
        (re.compile(r"\bFlask\s*\(\s*__name__"), "creates the Flask app"),
        (re.compile(r"^package main\b[\s\S]*\bfunc main\s*\(", re.M), "Go main package"),
        (re.compile(r"\bfn main\s*\(\s*\)"), "Rust main"),
        (re.compile(r"public\s+static\s+void\s+main\s*\("), "Java main"),
        (re.compile(r"@SpringBootApplication"), "Spring Boot application"),
        (re.compile(r"\bcreateRoot\s*\(|ReactDOM\.render\s*\("), "mounts the React app"),
        (re.compile(r"\bcreateApp\s*\("), "creates the Vue app"),
        (re.compile(r"\bexpress\s*\(\s*\)"), "creates the Express app"),
        (re.compile(r"\.listen\s*\(\s*(?:process\.env\.PORT|PORT|\d{2,5})"), "starts a server"),
    ]
    for f in files:
        text = texts.get(f)
        if not text or os.path.splitext(f)[1] not in (".py", ".js", ".ts", ".tsx", ".jsx", ".mjs", ".go", ".rs", ".java", ".kt"):
            continue
        if TEST_PATH.search(f):
            continue
        for rx, why in patterns:
            if rx.search(text):
                add(f, why)
                break
    for f in files:
        base = os.path.basename(f)
        if base in ("manage.py", "wsgi.py", "asgi.py", "main.rs", "lib.rs", "index.html") and f.count("/") <= 2:
            add(f, "conventional entry file")
        if re.search(r"(^|/)app/(layout|page)\.(t|j)sx?$", f) or re.search(r"(^|/)pages/_app\.(t|j)sx?$", f):
            add(f, "Next.js app root")
    return [{"path": p, "why": w} for p, w in sorted(eps.items())][:40]


def git_facts(root, files_set):
    head = run_git(root, "rev-parse", "HEAD")
    if not head:
        return {"is_repo": False}, {}
    facts = {"is_repo": True, "head": head.strip(), "short": head.strip()[:7]}
    branch = run_git(root, "branch", "--show-current")
    facts["branch"] = (branch or "").strip() or None
    remote = run_git(root, "remote", "get-url", "origin")
    remote = (remote or "").strip()
    facts["remote"] = remote or None
    m = re.search(r"github\.com[:/]([\w.\-]+)/([\w.\-]+?)(?:\.git)?$", remote)
    facts["github"] = ("https://github.com/%s/%s" % (m.group(1), m.group(2))) if m else None
    dirty = run_git(root, "status", "--porcelain", "--untracked-files=no")
    facts["dirty"] = bool(dirty and dirty.strip())
    log = run_git(root, "log", "--no-merges", "-n", "3000", "--date=short",
                  "--pretty=format:\x1e%H\t%ad\t%an\t%s", "--name-only")
    commits, churn = [], Counter()
    for chunk in (log or "").split("\x1e"):
        lines = [l for l in chunk.strip().splitlines() if l.strip()]
        if not lines:
            continue
        parts = lines[0].split("\t", 3)
        if len(parts) < 4:
            continue
        touched = [posix(l.strip()) for l in lines[1:]]
        for t in touched:
            if t in files_set:
                churn[t] += 1
        commits.append({"hash": parts[0][:7], "date": parts[1], "author": parts[2],
                        "subject": parts[3][:160], "files": len(touched),
                        "touched": [t for t in touched if t in files_set][:12]})
    facts["commits"] = len(commits)
    facts["authors"] = len({c["author"] for c in commits})
    if commits:
        facts["first_commit"] = commits[-1]["date"]
        facts["last_commit"] = commits[0]["date"]
    weeks = Counter()
    for c in commits:
        try:
            d = dt.date.fromisoformat(c["date"])
        except ValueError:
            continue
        weeks[(d - dt.timedelta(days=d.weekday())).isoformat()] += 1
    facts["timeline"] = [{"week": w, "commits": n} for w, n in sorted(weeks.items())]
    facts["log"] = commits[:400]
    return facts, churn


def session_facts(root):
    dirs = claude_project_dirs(root)
    files = []
    for d in dirs:
        for name in os.listdir(d):
            if name.endswith(".jsonl"):
                files.append(os.path.join(d, name))
    if not files:
        return {"found": False}
    mtimes = sorted(os.path.getmtime(f) for f in files)
    fmt = lambda t: dt.datetime.fromtimestamp(t).strftime("%Y-%m-%d")  # noqa: E731
    return {"found": True, "count": len(files), "dirs": dirs, "first": fmt(mtimes[0]), "last": fmt(mtimes[-1]),
            "megabytes": round(sum(os.path.getsize(f) for f in files) / 1e6, 1)}


def scan(root):
    root = os.path.abspath(root)
    paths = list_files(root)
    texts, records = {}, []
    for p in paths:
        lang = lang_of(p)
        kind = kind_of(p, lang)
        abs_p = os.path.join(root, p)
        size = os.path.getsize(abs_p) if os.path.exists(abs_p) else 0
        text = None if kind in ("asset", "lock") or is_binary_path(p) else read_text(abs_p)
        rec = {"path": p, "lang": lang, "kind": kind, "bytes": size, "lines": 0}
        if text is not None:
            texts[p] = text
            rec["lines"] = text.count("\n") + (1 if text and not text.endswith("\n") else 0)
            rec["sha1"] = hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()[:12]
        elif kind not in ("asset", "lock", "data"):
            rec["kind"] = "asset" if size else rec["kind"]
        records.append(rec)

    res = Resolver(root, paths, texts)
    imported_by = Counter()
    ext_usage = Counter()
    env = defaultdict(set)
    todos = []
    for rec in records:
        text = texts.get(rec["path"])
        if text is None or rec["kind"] not in ("source", "test", "config"):
            continue
        if rec["kind"] in ("source", "test"):
            internal, external = extract_imports(rec["path"], text, res)
            rec["imports"] = internal
            if external:
                rec["external"] = external[:40]
            for i in internal:
                imported_by[i] += 1
            for e in external:
                ext_usage[e] += 1
        for rx in ENV_RES:
            for name in rx.findall(text):
                env[name].add(rec["path"])
        if os.path.basename(rec["path"]).startswith(".env"):
            for name in ENV_FILE_LINE.findall(text):
                env[name].add(rec["path"])
        if len(todos) < 200 and rec["kind"] in ("source", "test"):
            for i, line in enumerate(text.splitlines(), 1):
                m = TODO_RE.search(line)
                if m:
                    todos.append({"path": rec["path"], "line": i, "tag": m.group(1), "text": m.group(2).strip(" */->")})
                    if len(todos) >= 200:
                        break

    git, churn = git_facts(root, set(paths))
    manifests = parse_manifests(paths, texts)
    entrypoints = find_entrypoints(paths, texts, manifests)
    ep_set = {e["path"] for e in entrypoints}

    for rec in records:
        p = rec["path"]
        rec["imported_by"] = imported_by.get(p, 0)
        rec["churn"] = churn.get(p, 0)
        if rec["kind"] not in ("source", "test", "config", "doc"):
            rec["score"] = 0
            continue
        s = 3.0 * math.log2(1 + rec["imported_by"]) + 1.5 * math.log2(1 + rec["churn"])
        s += 1.0 * math.log2(1 + rec["lines"] / 40.0) + (4.0 if p in ep_set else 0.0)
        base = os.path.basename(p).lower()
        if base in ("readme.md", "claude.md", "agents.md", "architecture.md"):
            s += 5.0
        if rec["kind"] == "test":
            s *= 0.45
        elif rec["kind"] in ("config", "doc"):
            s *= 0.6
        rec["score"] = s
    top = max([r["score"] for r in records] + [1e-9])
    for rec in records:
        rec["score"] = round(100 * rec["score"] / top, 1)

    by_lang = defaultdict(lambda: [0, 0])
    for rec in records:
        if rec["kind"] in ("source", "test") or (rec["kind"] == "config" and rec["lang"] in CODE_LANGS):
            by_lang[rec["lang"]][0] += 1
            by_lang[rec["lang"]][1] += rec["lines"]
    total_lines = sum(v[1] for v in by_lang.values()) or 1
    languages = sorted(
        ({"lang": k, "files": v[0], "lines": v[1], "share": round(100.0 * v[1] / total_lines, 1)} for k, v in by_lang.items()),
        key=lambda x: -x["lines"],
    )

    mods = defaultdict(lambda: {"files": 0, "lines": 0})
    edges = Counter()
    for rec in records:
        if rec["kind"] not in ("source", "test"):
            continue
        m = module_of(rec["path"])
        mods[m]["files"] += 1
        mods[m]["lines"] += rec["lines"]
        for i in rec.get("imports", []):
            mi = module_of(i)
            if mi != m:
                edges[(m, mi)] += 1
    modules = sorted(({"name": k, **v} for k, v in mods.items()), key=lambda x: -x["lines"])
    module_edges = [{"from": a, "to": b, "weight": w} for (a, b), w in edges.most_common(80)]

    docs = [r["path"] for r in records if r["kind"] == "doc" and (
        r["path"].count("/") == 0 or r["path"].lower().startswith(("docs/", "doc/")) or
        os.path.basename(r["path"]).lower() in ("claude.md", "agents.md", "architecture.md", "contributing.md"))][:40]

    counts = Counter(r["kind"] for r in records)
    return {
        "schema": 1,
        "tool": "onramp " + VERSION,
        "generated_at": dt.datetime.now().isoformat(timespec="seconds"),
        "root": root,
        "name": os.path.basename(root.rstrip("\\/")),
        "summary": {
            "files": len(records), "source_files": counts.get("source", 0), "test_files": counts.get("test", 0),
            "lines": sum(r["lines"] for r in records if r["kind"] in ("source", "test")),
            "kinds": dict(counts),
        },
        "languages": languages,
        "manifests": manifests,
        "entrypoints": entrypoints,
        "external_packages": [{"name": k, "files": v} for k, v in ext_usage.most_common(60)],
        "env_vars": [{"name": k, "files": sorted(v)[:8]} for k, v in sorted(env.items())][:120],
        "todos": todos,
        "modules": modules,
        "module_edges": module_edges,
        "docs": docs,
        "git": git,
        "sessions": session_facts(root),
        "files": records,
    }


def print_summary(data, out_path):
    s, g = data["summary"], data["git"]
    w = print
    w("ONRAMP SCAN  %s  ->  %s" % (data["name"], out_path))
    w("files %d (source %d, tests %d), %d lines of code" % (s["files"], s["source_files"], s["test_files"], s["lines"]))
    w("languages: " + ", ".join("%s %.0f%%" % (l["lang"], l["share"]) for l in data["languages"][:8]))
    if g.get("is_repo"):
        w("git: %s commits by %s author(s), %s -> %s, head %s%s" % (
            g.get("commits"), g.get("authors"), g.get("first_commit"), g.get("last_commit"), g.get("short"),
            " (uncommitted changes)" if g.get("dirty") else ""))
    else:
        w("git: not a repository")
    ss = data["sessions"]
    w("claude sessions: " + ("%d transcript(s), %s -> %s, %.1f MB" % (ss["count"], ss["first"], ss["last"], ss["megabytes"]) if ss.get("found") else "none found"))
    w("\nmanifests:")
    for m in data["manifests"][:15]:
        extra = ""
        if m.get("scripts"):
            extra = " scripts: " + ", ".join(list(m["scripts"])[:8])
        if m.get("deps"):
            extra += " | deps: " + ", ".join(m["deps"][:12]) + (" ..." if len(m["deps"]) > 12 else "")
        if m.get("services"):
            extra += " services: " + ", ".join(m["services"])
        w("  %s [%s]%s" % (m["path"], m.get("type"), extra))
    w("\nentry points:")
    for e in data["entrypoints"][:20]:
        w("  %s  (%s)" % (e["path"], e["why"]))
    w("\nread first (importance):")
    ranked = sorted((r for r in data["files"] if r.get("score")), key=lambda r: -r["score"])
    for r in ranked[:30]:
        w("  %5.1f  %-60s %5d lines  used by %d" % (r["score"], r["path"], r["lines"], r["imported_by"]))
    w("\nmodules (lines):  " + ", ".join("%s %d" % (m["name"], m["lines"]) for m in data["modules"][:14]))
    if data["module_edges"]:
        w("module edges:  " + ", ".join("%s->%s(%d)" % (e["from"], e["to"], e["weight"]) for e in data["module_edges"][:20]))
    if data["env_vars"]:
        w("env vars: " + ", ".join(e["name"] for e in data["env_vars"][:30]))
    if data["docs"]:
        w("docs: " + ", ".join(data["docs"][:15]))
    if data["todos"]:
        w("todo/fixme: %d (first: %s:%d %s)" % (len(data["todos"]), data["todos"][0]["path"], data["todos"][0]["line"], data["todos"][0]["text"][:60]))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("repo", nargs="?", default=".")
    ap.add_argument("--out")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args(argv)
    if not os.path.isdir(args.repo):
        sys.exit("onramp: not a directory: %s" % args.repo)
    data = scan(args.repo)
    out = args.out or os.path.join(onramp_dir(args.repo), "scan.json")
    save_json(out, data)
    if not args.quiet:
        print_summary(data, out)


if __name__ == "__main__":
    main()
