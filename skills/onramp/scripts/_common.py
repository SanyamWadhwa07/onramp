"""Shared helpers for the Onramp scripts. Standard library only (Python 3.8+)."""
import json
import os
import re
import subprocess

VERSION = "1.0.3"

IGNORE_DIRS = {
    ".git", ".hg", ".svn", "node_modules", ".venv", "venv", "env", "__pycache__",
    "dist", "build", ".next", ".nuxt", ".output", ".svelte-kit", ".turbo", ".cache",
    ".parcel-cache", "out", "target", "vendor", ".idea", ".vscode", "coverage",
    ".pytest_cache", ".mypy_cache", ".ruff_cache", ".tox", ".gradle", "obj",
    ".terraform", ".expo", ".dart_tool", ".angular", "site-packages", "Pods",
    ".onramp", ".DS_Store", "bower_components", ".yarn", ".pnpm-store",
}

LANGS = {
    ".py": "Python", ".pyi": "Python", ".ipynb": "Jupyter",
    ".js": "JavaScript", ".jsx": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".ts": "TypeScript", ".tsx": "TypeScript", ".mts": "TypeScript", ".cts": "TypeScript",
    ".vue": "Vue", ".svelte": "Svelte", ".astro": "Astro",
    ".go": "Go", ".rs": "Rust", ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin",
    ".scala": "Scala", ".swift": "Swift", ".m": "Objective-C", ".mm": "Objective-C",
    ".c": "C", ".h": "C", ".cc": "C++", ".cpp": "C++", ".cxx": "C++", ".hpp": "C++", ".hh": "C++",
    ".cs": "C#", ".fs": "F#", ".rb": "Ruby", ".php": "PHP", ".ex": "Elixir", ".exs": "Elixir",
    ".erl": "Erlang", ".hs": "Haskell", ".ml": "OCaml", ".clj": "Clojure", ".dart": "Dart",
    ".lua": "Lua", ".r": "R", ".jl": "Julia", ".zig": "Zig", ".nim": "Nim", ".sol": "Solidity",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell", ".ps1": "PowerShell",
    ".sql": "SQL", ".prisma": "Prisma", ".graphql": "GraphQL", ".gql": "GraphQL", ".proto": "Protobuf",
    ".html": "HTML", ".htm": "HTML", ".css": "CSS", ".scss": "SCSS", ".sass": "SCSS", ".less": "Less",
    ".md": "Markdown", ".mdx": "MDX", ".rst": "reStructuredText", ".txt": "Text",
    ".json": "JSON", ".yaml": "YAML", ".yml": "YAML", ".toml": "TOML", ".ini": "INI", ".cfg": "INI",
    ".xml": "XML", ".tf": "Terraform", ".hcl": "HCL", ".nix": "Nix",
}
FILENAME_LANGS = {
    "Dockerfile": "Docker", "Makefile": "Make", "Procfile": "Procfile", "Gemfile": "Ruby",
    "Rakefile": "Ruby", "Justfile": "Just", "CMakeLists.txt": "CMake",
}
CODE_LANGS = {
    "Python", "JavaScript", "TypeScript", "Vue", "Svelte", "Astro", "Go", "Rust", "Java", "Kotlin",
    "Scala", "Swift", "Objective-C", "C", "C++", "C#", "F#", "Ruby", "PHP", "Elixir", "Erlang",
    "Haskell", "OCaml", "Clojure", "Dart", "Lua", "R", "Julia", "Zig", "Nim", "Solidity", "Shell",
    "PowerShell", "SQL", "Prisma", "GraphQL", "Protobuf", "HTML", "CSS", "SCSS", "Less", "Jupyter",
    "Terraform", "HCL", "Nix", "Docker", "Make",
}
BINARY_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".bmp", ".tiff", ".svg", ".avif",
    ".woff", ".woff2", ".ttf", ".otf", ".eot", ".mp3", ".mp4", ".wav", ".ogg", ".webm", ".mov",
    ".zip", ".gz", ".tgz", ".bz2", ".xz", ".7z", ".rar", ".jar", ".war", ".pdf", ".exe", ".dll",
    ".so", ".dylib", ".a", ".o", ".class", ".pyc", ".pkl", ".pickle", ".pt", ".pth", ".bin",
    ".onnx", ".h5", ".npy", ".npz", ".parquet", ".feather", ".arrow", ".db", ".sqlite", ".sqlite3",
    ".lock", ".map", ".wasm", ".psd", ".sketch", ".fig", ".ckpt", ".safetensors",
}
DATA_EXT = {".csv", ".tsv", ".jsonl", ".ndjson", ".parquet", ".arrow", ".feather", ".npy", ".npz"}
LOCKFILES = {
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml", "poetry.lock", "Cargo.lock", "Gemfile.lock",
    "composer.lock", "go.sum", "bun.lockb", "uv.lock", "Pipfile.lock", "mix.lock", "pubspec.lock",
}
MAX_READ_BYTES = 1_500_000

# [[path]]  [[path:12]]  [[path:12-30|anchor text]]
CITE_RE = re.compile(r"\[\[([^\[\]|:\n]+?)(?::(\d+)(?:-(\d+))?)?(?:\|(.+?))?\]\](?!\])")


def posix(path):
    return path.replace("\\", "/")


def lang_of(path):
    name = os.path.basename(path)
    if name in FILENAME_LANGS:
        return FILENAME_LANGS[name]
    if name.startswith("Dockerfile"):
        return "Docker"
    return LANGS.get(os.path.splitext(name)[1].lower(), "Other")


def is_binary_path(path):
    return os.path.splitext(path)[1].lower() in BINARY_EXT


def read_text(abs_path, limit=MAX_READ_BYTES):
    """Return file text, or None for binary/unreadable/oversized files."""
    try:
        if os.path.getsize(abs_path) > limit:
            return None
        with open(abs_path, "rb") as fh:
            raw = fh.read()
    except OSError:
        return None
    if b"\x00" in raw[:8192]:
        return None
    return raw.decode("utf-8", errors="replace")


def read_lines(abs_path):
    text = read_text(abs_path, limit=MAX_READ_BYTES * 4)
    if text is None:
        return None
    return text.splitlines()


def norm_ws(text):
    return re.sub(r"\s+", " ", text).strip()


def run_git(root, *args):
    try:
        out = subprocess.run(
            ["git", "-C", root] + list(args), capture_output=True, timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if out.returncode != 0:
        return None
    return out.stdout.decode("utf-8", errors="replace")


def is_agent_skill_path(path):
    """Installed agent skills (.claude/skills/, .agents/skills/, .cursor/skills/ ...) are not the project's code."""
    parts = path.split("/")
    return any(parts[i].startswith(".") and parts[i + 1] == "skills" for i in range(len(parts) - 1))


def list_files(root):
    """Repo-relative POSIX paths. Uses git (respects .gitignore) when possible."""
    out = run_git(root, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
    files = []
    if out is not None:
        for p in out.split("\0"):
            if not p:
                continue
            parts = p.split("/")
            if any(part in IGNORE_DIRS for part in parts[:-1]) or is_agent_skill_path(p):
                continue
            if os.path.isfile(os.path.join(root, p)):
                files.append(p)
        if files:
            return sorted(set(files))
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS and not d.startswith(".")]
        for name in filenames:
            rel = posix(os.path.relpath(os.path.join(dirpath, name), root))
            if not is_agent_skill_path(rel):
                files.append(rel)
    return sorted(files)


def claude_project_dirs(root):
    """Claude Code transcript folders for this project (and sessions started in its subfolders)."""
    bases = []
    env = os.environ.get("CLAUDE_CONFIG_DIR")
    if env:
        bases.append(env)
    bases.append(os.path.join(os.path.expanduser("~"), ".claude"))
    encoded = re.sub(r"[^A-Za-z0-9]", "-", os.path.abspath(root).rstrip("\\/")).lower()
    found, seen = [], set()
    for base in bases:
        projects = os.path.join(base, "projects")
        if not os.path.isdir(projects):
            continue
        for name in os.listdir(projects):
            low = name.lower()
            if low == encoded or low.startswith(encoded + "-"):
                full = os.path.join(projects, name)
                real = os.path.normcase(os.path.realpath(full))
                if os.path.isdir(full) and real not in seen:
                    seen.add(real)
                    found.append(full)
    return found


def load_json(path):
    with open(path, "r", encoding="utf-8") as fh:
        try:
            return json.load(fh)
        except json.JSONDecodeError as e:
            raise SystemExit("onramp: %s is not valid JSON: %s at line %d, column %d" % (path, e.msg, e.lineno, e.colno))


def save_json(path, data, indent=None):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=indent)
        fh.write("\n")


def onramp_dir(root):
    return os.path.join(os.path.abspath(root), ".onramp")
