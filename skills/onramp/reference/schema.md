# guide.json reference

`.onramp/guide.json` is the single source of the guide. `render.py` turns it into the
interactive page and `GUIDE.md`; `verify.py` checks it. Write it as UTF-8 JSON.

Large guides can be written in pieces: put a JSON **array** in `.onramp/work/<key>.<name>.json`
(for example `work/lessons.flows.json`, `work/files.backend.json`) and run
`verify.py --merge`. Mergeable keys: `lessons files flows concepts decisions risks stack milestones exercises`.
Items are matched by `path` (files), `term` (concepts), `name` (stack), `title` (milestones,
exercises, decisions, risks) or `id` (lessons, flows); a fragment item replaces the guide item it
matches. Check one fragment on its own with `verify.py <repo> --fragment <file>`.

## Citations

Every string in the guide may contain citations. They are the only way to point at code.

| Form | Meaning |
|---|---|
| `[[backend/main.py]]` | a file or folder (checked: exists) |
| `[[backend/main.py:41-58\|def create_app(]]` | lines 41–58, and the text `def create_app(` appears in them |
| `[[backend/main.py:41\|app = FastAPI(]]` | a single line |

Rules:
- Paths are repo-relative with forward slashes.
- A line citation **must** have an anchor: an exact substring copied from those lines
  (an identifier, a signature, a distinctive string). Keep it short (under 60 characters).
  It may contain `|` and may end in `]` (as in `Tuple[str, int]`), but must not contain `]]`.
  Whitespace differences are ignored.
- Cite only files present in the working tree. Files deleted but not committed cannot be cited.
- Cite tight ranges: the function or block that proves the claim, usually 3–40 lines.
- Citations render as chips; clicking one shows the real code from the file.

## Top level

```json
{
  "schema": 1,
  "project": {
    "name": "PaperMind",
    "one_liner": "Upload a research paper and get a structured summary, a knowledge graph and answers to your questions.",
    "what": "Markdown. What it is, who it is for, the problem it solves. 2-4 sentences.",
    "analogy": "One everyday comparison for the whole system.",
    "audience": "Who uses it.",
    "status": "prototype | active | production | archived",
    "author": "optional: who wrote it, credited in the guide",
    "license": "optional: e.g. MIT"
  },
  "numbers": [{"value": "31.5k", "label": "lines of code", "note": "optional"}],
  "lessons": [ ... ],
  "quickstart": { ... },
  "stack": [ ... ],
  "architecture": { ... },
  "concepts": [ ... ],
  "flows": [ ... ],
  "data": { ... },
  "files": [ ... ],
  "milestones": [ ... ],
  "history": { ... },
  "decisions": [ ... ],
  "risks": [ ... ],
  "exercises": [ ... ]
}
```

Only `project` and `lessons` are required, but a complete guide fills every section.
`verification` is added by `verify.py`; never write it yourself.

## Lessons: the stops on the route

A lesson teaches one idea. The viewer builds personal routes out of lessons, so each one must
make sense on its own and say how long it takes.

```json
{
  "id": "flow-upload",
  "chapter": "flows",
  "title": "What happens when you upload a paper",
  "tier": "core",
  "minutes": 8,
  "goals": ["gist", "ship", "own"],
  "for": [],
  "summary": "One or two sentences a reader could stop at and still have the point.",
  "body": "Markdown with [[citations]]. 120-350 words. Plain words first, then the detail.",
  "deeper": "Optional markdown for 'Go deeper': edge cases, internals, numbers.",
  "show": [{"view": "flow", "id": "upload-paper"}],
  "diagram": "optional mermaid source",
  "checkpoint": {
    "q": "Where does the PDF text get split into sections?",
    "choices": ["In the React upload page", "In core/pipeline/pdf_extractor.py", "In the database"],
    "answer": 1,
    "explain": "The browser only sends the file; extraction happens server-side in [[core/pipeline/pdf_extractor.py]]."
  }
}
```

| Field | Values |
|---|---|
| `chapter` | `gist` `run` `stack` `map` `concepts` `flows` `data` `files` `built` `why` `care` `practice` |
| `tier` | `core`: essential, in every route. `standard`: a 1-day route. `deep`: 3-day and 1-week routes |
| `minutes` | honest reading-and-thinking time for someone who knows the stack (the viewer scales it) |
| `goals` | which goals this stop serves: `gist` (understand), `ship` (make a change), `own` (maintain), `rebuild` (build it again). Omit for all |
| `for` | limit to a background: `new` (new to the stack), `know`, `senior`. Omit for everyone. Use `["new"]` for stack primers |
| `show` | structured views embedded under the body, see below |

Chapters, in order (the "exits" on the road):

| id | Title | What belongs here |
|---|---|---|
| `gist` | The gist | what it is, who uses it, the one-paragraph mental model |
| `run` | Run it | prerequisites, setup, env vars, how to see it working |
| `stack` | The stack | each technology, its job here, primers for newcomers |
| `map` | The map | architecture, layers, folder tour, module dependencies |
| `concepts` | Core ideas | the domain words and abstractions the code is built on |
| `flows` | How it flows | real user journeys traced through the code, step by step |
| `data` | Data and state | models, storage, caches, what lives where |
| `files` | File by file | the files that matter, grouped by area |
| `built` | How it was built | build order, history, how the project grew |
| `why` | Why it's like this | decisions, trade-offs, alternatives not taken |
| `care` | Handle with care | risks, fragile spots, missing tests, security notes |
| `practice` | Your first changes | exercises from easy to hard |

### Views for `show`

| View | Renders | Extra keys |
|---|---|---|
| `quickstart` | setup steps, env vars | |
| `stack` | the stack table | |
| `architecture` | `architecture.diagram` and layers | |
| `depmap` | module dependency graph computed by the scanner | |
| `languages` | language breakdown computed by the scanner | |
| `concepts` | glossary cards | |
| `flow` | a step-through of one flow | `"id": "<flow id>"` |
| `data` | data model diagram and entities | |
| `files` | file cards | `"paths": [..]` optional subset, else all |
| `file` | one file card | `"path": "..."` |
| `milestones` | the build-order milestones | |
| `timeline` | git activity and `history.eras` | |
| `decisions` | decision records | |
| `risks` | risk list | |
| `exercises` | exercises | |

## Structured sections

```json
"quickstart": {
  "prerequisites": ["Python 3.11+", "Node 20+", "Docker (optional)"],
  "steps": [{"title": "Install backend deps", "run": "pip install -r requirements.txt", "explain": "markdown, cite where the command comes from"}],
  "env": [{"name": "GROQ_API_KEY", "purpose": "LLM provider key", "required": true, "at": "[[core/llm/providers.py:20-31|GROQ_API_KEY]]"}],
  "verify": "How you know it works."
},
"stack": [{
  "name": "FastAPI", "category": "Backend framework",
  "role": "Serves the REST API the React app calls.",
  "why": "Async, typed request models, automatic docs.",
  "where": "[[backend/main.py:30-44|FastAPI(]]",
  "primer": "Plain-language intro for someone who has never used it."
}],
"architecture": {
  "summary": "markdown",
  "diagram": "flowchart LR\n  UI[\"React app\"] --> API[\"FastAPI\"]",
  "layers": [{"name": "API", "purpose": "HTTP routes and auth", "paths": ["backend/routes", "backend/auth"]}]
},
"concepts": [{"term": "Agent", "plain": "One-sentence definition in everyday words.", "detail": "markdown", "at": "[[core/agents/base_agent.py:12-40|class BaseAgent]]"}],
"flows": [{
  "id": "upload-paper", "title": "Upload a paper", "trigger": "User drops a PDF on the upload page",
  "summary": "markdown",
  "steps": [{"title": "Browser posts the file", "at": "[[frontend/src/lib/api.js:88-97|uploadPaper]]", "explain": "markdown"}]
}],
"data": {"summary": "markdown", "diagram": "erDiagram ...", "entities": [{"name": "Paper", "purpose": "...", "at": "[[...]]", "fields": ["id: uuid", "title: text"]}]},
"files": [{
  "path": "core/agents/orchestrator.py", "area": "Agents", "role": "Coordinates the agents for one paper.",
  "summary": "markdown, 2-5 sentences",
  "symbols": [{"name": "Orchestrator.run", "at": "[[core/agents/orchestrator.py:120-188|async def run(]]", "does": "..."}],
  "read_when": "You need to change the order agents run in.",
  "complexity": 4,
  "gotchas": "optional markdown"
}],
"milestones": [{
  "title": "A FastAPI skeleton that answers /health", "goal": "markdown",
  "files": ["backend/main.py"], "concepts": ["Routes"],
  "explain": "markdown", "try": "A hands-on task to do yourself at this stage."
}],
"history": {"summary": "markdown", "eras": [{"title": "Prototype", "when": "Nov 2025", "what": "markdown citing commits like `a1b2c3d`"}]},
"decisions": [{
  "title": "Local LLMs through Ollama as a fallback", "choice": "markdown", "why": "markdown",
  "tradeoff": "markdown", "evidence": "markdown: citations, commit hashes, doc quotes, session quotes",
  "source": "documented | inferred"
}],
"risks": [{"title": "...", "severity": "high | medium | low", "at": "[[...]]", "why": "markdown", "advice": "markdown"}],
"exercises": [{"title": "...", "level": "easy | medium | hard", "goal": "markdown", "files": ["..."], "hints": ["..."], "done_when": "markdown"}]
```

## How routes are built (viewer and tutor use the same rules)

1. **Budget** in minutes: 1 hour = 60, 1 day = 360, 3 days = 3 × 300, 1 week = 5 × 300.
2. **Scale** each lesson's minutes: new to the stack × 1.3, senior × 0.7.
3. **Candidates**: drop lessons whose `for` excludes the reader's background.
4. **Priority**: core 30, standard 20, deep 10; +8 if `goals` includes the reader's goal;
   +0 to +6 from the chapter's weight for that goal (below).
5. **Pick**: every core lesson, always (they tell the whole story, so the shortest route may run
   slightly over for newcomers), then the rest by priority while they fit. Longer routes also get
   hands-on stops made from the guide: reading a key file in full (lines / 30 minutes, 10 to 60;
   all goals), each exercise (easy 30, medium 60, hard 120 minutes; ship, own, rebuild) and each
   milestone's `try` (60 minutes; rebuild). They rank below lessons and only join routes whose
   goal they serve.
6. **Order** by the goal's chapter order, then by position in the guide:
   - gist: gist map stack concepts flows data why built files care run practice
   - ship: gist run map flows files care practice stack concepts data why built
   - own: gist run stack map concepts flows data files built why care practice
   - rebuild: gist stack built map concepts data flows files why care run practice
7. **Days**: fill each day up to its share of the budget; the last stop of each day is a rest stop.
