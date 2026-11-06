(function () {
  "use strict";

  // ------------------------------------------------------------------ data
  var D = JSON.parse(document.getElementById("onramp-data").textContent || "{}");
  var G = D.guide || {}, S = D.scan || {}, SNIP = D.snippets || {}, SRC = D.sources || {};
  var SESS = D.sessions || null, META = D.meta || {};
  var P = G.project || {};
  var LESSONS = (G.lessons || []).filter(function (l) { return l && l.id; });
  var BYID = {};
  LESSONS.forEach(function (l, i) { l._i = i; BYID[l.id] = l; });
  var CHAPTERS = [
    ["gist", "The gist", "the gist"], ["run", "Run it", "running it"], ["stack", "The stack", "the stack"],
    ["map", "The map", "the map"], ["concepts", "Core ideas", "core ideas"], ["flows", "How it flows", "the flows"],
    ["data", "Data and state", "the data"], ["files", "File by file", "the files"],
    ["built", "How it was built", "how it was built"], ["why", "Why it's like this", "the why"],
    ["care", "Handle with care", "the risks"], ["practice", "Your first changes", "practice"]
  ];
  var CH = {};
  CHAPTERS.forEach(function (c, i) { CH[c[0]] = { n: i + 1, title: c[1], short: c[2] }; });
  var FILES = S.files || [];
  var FBY = {};
  FILES.forEach(function (f) { FBY[f.p] = f; });
  var CARDS = {};
  (G.files || []).forEach(function (f) { if (f && f.path) CARDS[f.path] = f; });
  var FLOWS = {};
  (G.flows || []).forEach(function (f) { if (f && f.id) FLOWS[f.id] = f; });

  // Hands-on stops built from the guide's own content. They only make it into longer routes:
  // reading a key file in full, doing an exercise, building a milestone yourself.
  var EXTRAS = [];
  (G.exercises || []).forEach(function (x, i) {
    EXTRAS.push({ id: "do-exercise-" + (i + 1), chapter: "practice", tier: "deep", extra: true,
      minutes: { easy: 30, medium: 60, hard: 120 }[x.level] || 45, goals: ["ship", "own", "rebuild"],
      title: "Do it: " + x.title, summary: x.goal || "", show: [{ view: "exercise", index: i }] });
  });
  (G.milestones || []).forEach(function (m, i) {
    if (!m["try"]) return;
    EXTRAS.push({ id: "build-milestone-" + (i + 1), chapter: "built", tier: "deep", extra: true, minutes: 60,
      goals: ["rebuild"], title: "Build it: " + m.title, summary: m["try"], show: [{ view: "milestone", index: i }] });
  });
  (G.files || []).forEach(function (c) {
    var f = FBY[c.path];
    if (!f || !f.n) return;
    EXTRAS.push({ id: "read-" + c.path.replace(/[^A-Za-z0-9]+/g, "-").toLowerCase(), chapter: "files", tier: "deep", extra: true,
      minutes: Math.max(10, Math.min(60, Math.round(f.n / 30))), goals: ["gist", "own", "ship", "rebuild"],
      title: "Read " + c.path, summary: c.role || c.summary || "", show: [{ view: "file", path: c.path }] });
  });
  EXTRAS.forEach(function (x, i) { x._i = LESSONS.length + i; BYID[x.id] = x; });

  var TIMES = [
    { id: "h1", label: "1 hour", sub: "The essentials", budget: 60, segs: ["The hour"] },
    { id: "d1", label: "1 day", sub: "Working knowledge", budget: 360, segs: ["Morning", "Midday", "Afternoon"] },
    { id: "d3", label: "3 days", sub: "A confident contributor", budget: 900, segs: ["Day 1", "Day 2", "Day 3"] },
    { id: "w1", label: "1 week", sub: "Know it inside out", budget: 1500, segs: ["Day 1", "Day 2", "Day 3", "Day 4", "Day 5"] }
  ];
  var GOALS = [
    { id: "gist", label: "Get the gist", sub: "What it is and how the pieces fit" },
    { id: "ship", label: "Ship a change", sub: "The shortest road to your first change" },
    { id: "own", label: "Own it", sub: "Maintain it, debug it, review it" },
    { id: "rebuild", label: "Rebuild it", sub: "Learn it by building it in order" }
  ];
  var BGS = [
    { id: "new", label: "New to this stack", sub: "Explain the tools as well", scale: 1.3 },
    { id: "know", label: "I know the stack", sub: "Focus on this project", scale: 1 },
    { id: "senior", label: "Senior", sub: "Skip the basics, keep it dense", scale: 0.7 }
  ];
  var ORDER = {
    gist: ["gist", "map", "stack", "concepts", "flows", "data", "why", "built", "files", "care", "run", "practice"],
    ship: ["gist", "run", "map", "flows", "files", "care", "practice", "stack", "concepts", "data", "why", "built"],
    own: ["gist", "run", "stack", "map", "concepts", "flows", "data", "files", "built", "why", "care", "practice"],
    rebuild: ["gist", "stack", "built", "map", "concepts", "data", "flows", "files", "why", "care", "run", "practice"]
  };
  var MERMAID_URL = "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js";
  var HLJS_URL = "https://cdnjs.cloudflare.com/ajax/libs/highlight.js/11.9.0/highlight.min.js";
  var CITE_RE = /\[\[([^\[\]|:\n]+?)(?::(\d+)(?:-(\d+))?)?(?:\|(.+?))?\]\](?!\])/g;
  var LANG_COLORS = ["#2f7d5b", "#d39b1e", "#3f6fb5", "#b4553f", "#7a5bb5", "#4f9aa8", "#9a8a3a", "#b0517d", "#5e6b74"];

  // ------------------------------------------------------------------ helpers
  var main = document.getElementById("main");
  function $(s, el) { return (el || document).querySelector(s); }
  function $$(s, el) { return Array.prototype.slice.call((el || document).querySelectorAll(s)); }
  function esc(s) {
    return String(s == null ? "" : s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
  }
  function pad(n) { return (n < 10 ? "0" : "") + n; }
  function fmtMin(m) {
    m = Math.round(m);
    if (m < 60) return m + " min";
    var h = Math.floor(m / 60), r = m % 60;
    return h + " h" + (r ? " " + r + " m" : "");
  }
  function fmtNum(n) { return n == null ? "" : Number(n).toLocaleString("en-US"); }
  function base(p) { return String(p).split("/").pop(); }
  function cap(s) { return s ? s.charAt(0).toUpperCase() + s.slice(1) : s; }
  function joinAnd(list) {
    if (list.length <= 1) return list.join("");
    return list.slice(0, -1).join(", ") + " and " + list[list.length - 1];
  }
  var store = {
    get: function (k, d) { try { var v = localStorage.getItem(k); return v ? JSON.parse(v) : d; } catch (e) { return d; } },
    set: function (k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* storage unavailable */ } }
  };
  var KEY = "onramp:" + (P.name || "guide") + ":" + String(META.commit || "").slice(0, 7);
  var state = store.get(KEY, null) || { route: null, done: [], quiz: {} };
  state.done = state.done || []; state.quiz = state.quiz || {};
  function save() { store.set(KEY, state); }
  function isDone(id) { return state.done.indexOf(id) >= 0; }
  function loadScript(src) {
    return new Promise(function (res, rej) {
      var s = document.createElement("script");
      s.src = src; s.async = true; s.crossOrigin = "anonymous";
      s.onload = res; s.onerror = rej;
      document.head.appendChild(s);
    });
  }

  // ------------------------------------------------------------------ markdown
  function citeHTML(path, a, b, anchor) {
    path = path.trim();
    if (a) {
      var key = path + ":" + a + "-" + (b || a);
      var label = base(path) + ":" + a + (b && b !== a ? "–" + b : "");
      return '<button type="button" class="cite" data-cite="' + esc(key) + '" title="' + esc(path + (anchor ? "  ·  " + anchor : "")) + '">' + esc(label) + "</button>";
    }
    return '<button type="button" class="cite file" data-file="' + esc(path) + '" title="' + esc(path) + '">' + esc(path.length > 42 ? "…" + path.slice(-40) : path) + "</button>";
  }
  function inline(s) {
    var tokens = [];
    function ph(html) { tokens.push(html); return "\u0000" + (tokens.length - 1) + "\u0000"; }
    s = String(s == null ? "" : s);
    s = s.replace(CITE_RE, function (m, p, a, b, anc) { return ph(citeHTML(p, a, b, anc)); });
    s = s.replace(/`([^`]+)`/g, function (m, c) { return ph("<code>" + esc(c) + "</code>"); });
    s = esc(s);
    s = s.replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>");
    s = s.replace(/(^|[^*\w])\*([^*\n]+)\*(?!\w)/g, "$1<em>$2</em>");
    s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    return s.replace(/\u0000(\d+)\u0000/g, function (m, n) { return tokens[+n]; });
  }
  function md(src) {
    var lines = String(src == null ? "" : src).replace(/\r/g, "").split("\n"), out = [], i = 0;
    var BLOCK = /^(```|#{1,4}\s|\s*[-*]\s+|\s*\d+[.)]\s+|>)/;
    while (i < lines.length) {
      var line = lines[i], m, buf, items;
      if (/^```/.test(line)) {
        buf = []; i++;
        while (i < lines.length && !/^```/.test(lines[i])) buf.push(lines[i++]);
        i++;
        out.push("<pre><code>" + esc(buf.join("\n")) + "</code></pre>");
        continue;
      }
      if (/^\s*$/.test(line)) { i++; continue; }
      if ((m = line.match(/^(#{1,4})\s+(.*)$/))) {
        var lvl = Math.min(4, m[1].length + 2);
        out.push("<h" + lvl + ">" + inline(m[2]) + "</h" + lvl + ">"); i++; continue;
      }
      var ul = /^\s*[-*]\s+/, ol = /^\s*\d+[.)]\s+/;
      if (ul.test(line) || ol.test(line)) {
        var re = ul.test(line) ? ul : ol, tag = re === ul ? "ul" : "ol";
        items = [];
        while (i < lines.length && re.test(lines[i])) {
          var it = lines[i].replace(re, ""); i++;
          while (i < lines.length && /^\s{2,}\S/.test(lines[i]) && !re.test(lines[i])) it += " " + lines[i++].trim();
          items.push("<li>" + inline(it) + "</li>");
        }
        out.push("<" + tag + ">" + items.join("") + "</" + tag + ">");
        continue;
      }
      if (/^>\s?/.test(line)) {
        buf = [];
        while (i < lines.length && /^>\s?/.test(lines[i])) buf.push(lines[i++].replace(/^>\s?/, ""));
        out.push('<p class="muted">' + inline(buf.join(" ")) + "</p>");
        continue;
      }
      buf = [line]; i++;
      while (i < lines.length && !/^\s*$/.test(lines[i]) && !BLOCK.test(lines[i])) buf.push(lines[i++]);
      out.push("<p>" + inline(buf.join(" ")) + "</p>");
    }
    return out.join("");
  }

  // ------------------------------------------------------------------ route planner
  function buildRoute(cfg) {
    var t = TIMES.filter(function (x) { return x.id === cfg.time; })[0] || TIMES[1];
    var bg = BGS.filter(function (x) { return x.id === cfg.bg; })[0] || BGS[1];
    var goal = ORDER[cfg.goal] ? cfg.goal : "gist";
    var order = ORDER[goal];
    function weight(ch) { var i = order.indexOf(ch); return i < 0 ? 0 : Math.max(0, 6 - Math.floor(i / 2)); }
    var tierP = { core: 30, standard: 20, deep: 10 };
    var cands = LESSONS.concat(EXTRAS).filter(function (l) {
      if (l.extra && l.goals.indexOf(goal) < 0) return false;
      return !(l["for"] && l["for"].length) || l["for"].indexOf(bg.id) >= 0;
    })
      .map(function (l) {
        var serves = !(l.goals && l.goals.length) || l.goals.indexOf(goal) >= 0;
        var base = l.extra ? 5 : (tierP[l.tier] || 10);
        return { l: l, mins: Math.max(1, Math.round((l.minutes || 5) * bg.scale)), pr: base + (serves ? 8 : 0) + weight(l.chapter) };
      });
    function byPr(a, b) { return b.pr - a.pr || a.l._i - b.l._i; }
    var used = 0, picked = [];
    cands.filter(function (c) { return c.l.tier === "core"; }).sort(byPr).forEach(function (c) {
      if (used + c.mins <= t.budget || !picked.length) { picked.push(c); used += c.mins; }
    });
    cands.filter(function (c) { return c.l.tier !== "core"; }).sort(byPr).forEach(function (c) {
      if (used + c.mins <= t.budget) { picked.push(c); used += c.mins; }
    });
    function rank(ch) { var i = order.indexOf(ch); return i < 0 ? 99 : i; }
    picked.sort(function (a, b) { return rank(a.l.chapter) - rank(b.l.chapter) || a.l._i - b.l._i; });
    var n = t.segs.length, capMins = used / n, segs = [], cur = { name: t.segs[0], stops: [], mins: 0 };
    picked.forEach(function (s) {
      if (cur.stops.length && cur.mins + s.mins / 2 > capMins && segs.length < n - 1) {
        segs.push(cur); cur = { name: t.segs[segs.length], stops: [], mins: 0 };
      }
      cur.stops.push(s); cur.mins += s.mins;
    });
    segs.push(cur);
    segs.forEach(function (sg) {
      var seen = [];
      sg.stops.forEach(function (s) { var c = CH[s.l.chapter]; if (c && seen.indexOf(c.short) < 0) seen.push(c.short); });
      sg.title = cap(seen.length > 3 ? seen.slice(0, 3).join(", ") + " and more" : joinAnd(seen));
    });
    var stops = [];
    segs.forEach(function (sg, si) { sg.stops.forEach(function (s) { s.seg = si; stops.push(s); }); });
    return { time: t, goal: GOALS.filter(function (g) { return g.id === goal; })[0], bg: bg, segs: segs, stops: stops, mins: used, budget: t.budget };
  }
  function currentRoute() { return state.route ? buildRoute(state.route) : null; }

  // ------------------------------------------------------------------ shared bits
  function trustBadge() {
    var v = G.verification, b = $("#trust");
    if (v && v.citations) {
      b.innerHTML = '<b>' + fmtNum(v.verified) + "/" + fmtNum(v.citations) + '</b><span class="long">&nbsp;claims verified' + (v.commit ? " · " + esc(v.commit) : "") + "</span>";
      b.title = "Every citation was checked against the code";
    } else {
      b.className = "trust none";
      b.innerHTML = '<span class="long">not verified</span>';
    }
  }
  function footer() {
    var v = G.verification || {};
    return '<footer class="foot"><span>Generated by <a href="https://github.com/SanyamWadhwa07/onramp" target="_blank" rel="noopener">Onramp</a>' +
      (S.git && S.git.short ? " from commit <span class=\"mono\">" + esc(S.git.short) + "</span>" : "") +
      (v.checked_at ? " · checked " + esc(v.checked_at.slice(0, 10)) : "") + "</span>" +
      "<span>Every claim links to the code it comes from.</span></footer>";
  }
  function exitTab(ch) {
    var c = CH[ch] || { n: 0, title: ch };
    return '<span class="exit-tab"><span class="no">Exit ' + pad(c.n) + "</span>" + esc(c.title) + "</span>";
  }
  function mermaidBlock(src) {
    if (!src) return "";
    return '<div class="schematic mermaid-block"><div class="mermaid-out"></div><pre class="src">' + esc(src) + "</pre></div>";
  }
  function chips(paths) {
    return '<div class="chips">' + (paths || []).map(function (p) {
      return '<a class="chip-link" href="#files/' + esc(p) + '">' + esc(p) + "</a>";
    }).join("") + "</div>";
  }
  function lessonFor(pred) {
    for (var i = 0; i < LESSONS.length; i++) if (pred(LESSONS[i])) return LESSONS[i];
    return null;
  }

  // ------------------------------------------------------------------ views inside lessons
  var VIEWS = {
    quickstart: function () {
      var q = G.quickstart; if (!q) return "";
      var h = "";
      if (q.prerequisites && q.prerequisites.length) h += '<div class="chips">' + q.prerequisites.map(function (p) { return '<span class="pill">' + esc(p) + "</span>"; }).join("") + "</div>";
      if (q.steps && q.steps.length) {
        h += '<div class="flow">' + q.steps.map(function (s) {
          return '<div class="step"><div class="step-body"><h4>' + esc(s.title) + "</h4>" +
            (s.run ? '<div class="prose"><pre><code>' + esc(s.run) + "</code></pre></div>" : "") +
            (s.explain ? '<div class="prose">' + md(s.explain) + "</div>" : "") + "</div></div>";
        }).join("") + "</div>";
      }
      if (q.env && q.env.length) {
        h += '<div class="table-wrap"><table class="table"><thead><tr><th>Variable</th><th>What it does</th><th>Needed</th><th>Read at</th></tr></thead><tbody>' +
          q.env.map(function (e) {
            return "<tr><td class=\"mono\">" + esc(e.name) + "</td><td>" + inline(e.purpose) + "</td><td>" + (e.required ? "yes" : "optional") + "</td><td>" + inline(e.at || "") + "</td></tr>";
          }).join("") + "</tbody></table></div>";
      }
      if (q.verify) h += '<div class="prose"><p><strong>You know it works when:</strong> ' + inline(q.verify) + "</p></div>";
      return h;
    },
    stack: function () {
      var st = G.stack || []; if (!st.length) return "";
      var newbie = state.route && state.route.bg === "new";
      return '<div class="list-rows">' + st.map(function (s) {
        return '<div class="list-row"><b>' + esc(s.name) + '<br><span class="pill">' + esc(s.category || "") + "</span></b><div>" +
          "<p>" + inline(s.role) + "</p>" + (s.why ? '<p class="muted">' + inline(s.why) + "</p>" : "") +
          (s.where ? "<p>" + inline(s.where) + "</p>" : "") +
          (s.primer ? (newbie ? '<div class="prose"><p class="muted"><strong>New to it?</strong> ' + inline(s.primer) + "</p></div>"
            : '<details class="deeper"><summary>New to ' + esc(s.name) + "?</summary><div class=\"prose\"><p>" + inline(s.primer) + "</p></div></details>") : "") +
          "</div></div>";
      }).join("") + "</div>";
    },
    architecture: function () {
      var a = G.architecture; if (!a) return "";
      var h = a.summary ? '<div class="prose">' + md(a.summary) + "</div>" : "";
      h += mermaidBlock(a.diagram);
      if (a.layers && a.layers.length) {
        h += '<div class="list-rows">' + a.layers.map(function (l) {
          return '<div class="list-row"><b>' + esc(l.name) + "</b><div><p>" + inline(l.purpose) + "</p>" + chips(l.paths) + "</div></div>";
        }).join("") + "</div>";
      }
      return h;
    },
    depmap: function () {
      var edges = (S.module_edges || []).slice(0, 28);
      if (!edges.length) return '<p class="empty">No cross-module imports were detected.</p>';
      var lines = {}; (S.modules || []).forEach(function (m) { lines[m.name] = m.lines; });
      var ids = {}, n = 0, out = ["flowchart LR"];
      function id(name) {
        if (!ids[name]) { ids[name] = "m" + (++n); out.push("  " + ids[name] + '["' + name.replace(/"/g, "'") + (lines[name] ? "<br/><small>" + fmtNum(lines[name]) + " lines</small>" : "") + '"]'); }
        return ids[name];
      }
      edges.forEach(function (e) { var a = id(e.from), b = id(e.to); out.push("  " + a + " -->|" + e.weight + "| " + b); });
      return '<p class="muted">Computed from the imports in the code: an arrow means the left module imports the right one, and the number is how many imports.</p>' + mermaidBlock(out.join("\n"));
    },
    languages: function () {
      var L = (S.languages || []).slice(0, 8); if (!L.length) return "";
      return '<div class="langbar">' + L.map(function (l, i) { return '<i style="width:' + l.share + "%;background:" + LANG_COLORS[i % LANG_COLORS.length] + '" title="' + esc(l.lang) + '"></i>'; }).join("") +
        '</div><div class="legend">' + L.map(function (l, i) { return '<span><i style="background:' + LANG_COLORS[i % LANG_COLORS.length] + '"></i>' + esc(l.lang) + " " + l.share + "% · " + fmtNum(l.lines) + " lines</span>"; }).join("") + "</div>";
    },
    concepts: function () {
      var c = G.concepts || []; if (!c.length) return "";
      return '<div class="grid-cards">' + c.map(function (x) {
        return '<div class="mini"><h4>' + esc(x.term) + "</h4><p>" + inline(x.plain) + "</p>" + (x.detail ? '<div class="prose" style="font-size:.88rem">' + md(x.detail) + "</div>" : "") + (x.at ? "<p>" + inline(x.at) + "</p>" : "") + "</div>";
      }).join("") + "</div>";
    },
    flow: function (v) {
      var f = FLOWS[v.id]; if (!f) return "";
      return '<div class="view-flow" data-flow="' + esc(f.id) + '"><h3>' + esc(f.title) + "</h3>" +
        (f.trigger ? '<p class="muted">Starts when: ' + inline(f.trigger) + "</p>" : "") +
        (f.summary ? '<div class="prose">' + md(f.summary) + "</div>" : "") +
        '<div class="flow-controls"><button class="btn" type="button" data-flow-step="0">Step through it</button><span class="subtle mono" style="font-size:.76rem">' + (f.steps || []).length + " steps</span></div>" +
        '<div class="flow">' + (f.steps || []).map(function (s, i) {
          return '<div class="step" data-i="' + i + '"><div class="step-body"><h4>' + esc(s.title) + "</h4>" + (s.at ? "<div>" + inline(s.at) + "</div>" : "") + (s.explain ? "<p>" + inline(s.explain) + "</p>" : "") + "</div></div>";
        }).join("") + "</div></div>";
    },
    data: function () {
      var d = G.data; if (!d) return "";
      var h = d.summary ? '<div class="prose">' + md(d.summary) + "</div>" : "";
      h += mermaidBlock(d.diagram);
      if (d.entities && d.entities.length) {
        h += '<div class="grid-cards">' + d.entities.map(function (e) {
          return '<div class="mini"><h4>' + esc(e.name) + "</h4><p>" + inline(e.purpose) + "</p>" +
            (e.fields && e.fields.length ? '<div class="mono" style="font-size:.76rem;color:var(--muted)">' + e.fields.map(esc).join("<br>") + "</div>" : "") +
            (e.at ? "<p>" + inline(e.at) + "</p>" : "") + "</div>";
        }).join("") + "</div>";
      }
      return h;
    },
    files: function (v) {
      var list = (v.paths && v.paths.length ? v.paths.map(function (p) { return CARDS[p] || { path: p }; }) : (G.files || []));
      if (!list.length) return "";
      return '<div class="grid-cards">' + list.map(function (f) {
        return '<a class="mini" style="text-decoration:none;color:inherit" href="#files/' + esc(f.path) + '"><span class="eyebrow">' + esc(f.area || (FBY[f.path] || {}).l || "") + '</span><h4 class="mono" style="font-family:var(--font-mono);font-size:.84rem;word-break:break-all">' + esc(f.path) + "</h4><p>" + inline(f.role || f.summary || "") + "</p></a>";
      }).join("") + "</div>";
    },
    file: function (v) { return fileCard(v.path, true); },
    exercise: function (v) {
      var x = (G.exercises || [])[v.index]; if (!x) return "";
      return '<div class="mini"><span class="pill ' + (x.level === "hard" ? "high" : x.level === "medium" ? "medium" : "core") + '" style="justify-self:start">' + esc(x.level || "") + "</span>" +
        '<div class="prose">' + md(x.goal) + "</div>" + (x.files && x.files.length ? chips(x.files) : "") +
        (x.hints && x.hints.length ? '<details class="deeper"><summary>Hints</summary><div class="prose"><ul>' + x.hints.map(function (hh) { return "<li>" + inline(hh) + "</li>"; }).join("") + "</ul></div></details>" : "") +
        (x.done_when ? '<p class="try"><b>Done when:</b> ' + inline(x.done_when) + "</p>" : "") + "</div>";
    },
    milestone: function (v) {
      var m = (G.milestones || [])[v.index]; if (!m) return "";
      return '<ol class="milestones" start="' + (v.index + 1) + '" style="counter-reset: ms ' + v.index + '"><li class="milestone"><div class="body"><h3>' + esc(m.title) + "</h3>" +
        (m.goal ? '<div class="prose">' + md(m.goal) + "</div>" : "") + (m.files && m.files.length ? chips(m.files) : "") +
        (m.explain ? '<div class="prose">' + md(m.explain) + "</div>" : "") + "</div></li></ol>";
    },
    milestones: function () {
      var ms = G.milestones || []; if (!ms.length) return "";
      return '<ol class="milestones">' + ms.map(function (m) {
        return '<li class="milestone"><div class="body"><h3>' + esc(m.title) + "</h3>" + (m.goal ? '<div class="prose">' + md(m.goal) + "</div>" : "") +
          (m.files && m.files.length ? chips(m.files) : "") + (m.explain ? '<div class="prose">' + md(m.explain) + "</div>" : "") +
          (m["try"] ? '<p class="try"><b>Try it:</b> ' + inline(m["try"]) + "</p>" : "") + "</div></li>";
      }).join("") + "</ol>";
    },
    timeline: function () {
      var h = "", tl = (S.git && S.git.timeline) || [];
      if (tl.length) {
        var max = Math.max.apply(null, tl.map(function (w) { return w.commits; })), W = 720, H = 90, bw = Math.max(2, Math.min(18, (W - 20) / tl.length - 2));
        h += '<div class="schematic" style="padding:18px 16px 10px"><svg class="spark" viewBox="0 0 ' + W + " " + (H + 16) + '" preserveAspectRatio="none" role="img" aria-label="Commits per week">' +
          tl.map(function (w, i) { var x = 10 + i * ((W - 20) / tl.length), hh = Math.max(2, (w.commits / max) * H); return '<rect x="' + x.toFixed(1) + '" y="' + (H - hh).toFixed(1) + '" width="' + bw.toFixed(1) + '" height="' + hh.toFixed(1) + '" rx="1"><title>' + esc(w.week) + ": " + w.commits + " commits</title></rect>"; }).join("") +
          '<text class="axis" x="10" y="' + (H + 13) + '">' + esc(tl[0].week) + '</text><text class="axis" x="' + (W - 10) + '" y="' + (H + 13) + '" text-anchor="end">' + esc(tl[tl.length - 1].week) + "</text></svg>" +
          '<p class="subtle mono" style="font-size:.74rem">' + fmtNum(S.git.commits) + " commits by " + fmtNum(S.git.authors) + " author(s), " + esc(S.git.first_commit) + " → " + esc(S.git.last_commit) + "</p></div>";
      }
      var hist = G.history;
      if (hist) {
        if (hist.summary) h += '<div class="prose">' + md(hist.summary) + "</div>";
        if (hist.eras && hist.eras.length) h += '<div class="list-rows">' + hist.eras.map(function (e) {
          return '<div class="list-row"><b>' + esc(e.title) + '<br><span class="subtle mono" style="font-size:.74rem;font-weight:400">' + esc(e.when || "") + "</span></b><div class=\"prose\">" + md(e.what) + "</div></div>";
        }).join("") + "</div>";
      }
      return h;
    },
    decisions: function () {
      var ds = G.decisions || []; if (!ds.length) return "";
      return '<div class="list-rows">' + ds.map(function (d) {
        return '<div class="list-row"><b>' + esc(d.title) + '<br><span class="pill ' + esc(d.source || "") + '">' + esc(d.source || "") + "</span></b><div>" +
          (d.choice ? '<div class="prose"><p><strong>Choice:</strong> ' + inline(d.choice) + "</p></div>" : "") +
          (d.why ? '<div class="prose"><p><strong>Why:</strong> ' + inline(d.why) + "</p></div>" : "") +
          (d.tradeoff ? '<div class="prose"><p><strong>Trade-off:</strong> ' + inline(d.tradeoff) + "</p></div>" : "") +
          (d.evidence ? '<div class="prose"><p class="muted"><strong>Evidence:</strong> ' + inline(d.evidence) + "</p></div>" : "") + "</div></div>";
      }).join("") + "</div>";
    },
    risks: function () {
      var rs = G.risks || []; if (!rs.length) return "";
      return '<div class="list-rows">' + rs.map(function (r) {
        return '<div class="list-row"><b>' + esc(r.title) + '<br><span class="pill ' + esc(r.severity || "") + '">' + esc(r.severity || "") + "</span></b><div>" +
          (r.at ? "<div>" + inline(r.at) + "</div>" : "") + (r.why ? '<div class="prose">' + md(r.why) + "</div>" : "") +
          (r.advice ? '<p class="try"><b>What to do:</b> ' + inline(r.advice) + "</p>" : "") + "</div></div>";
      }).join("") + "</div>";
    },
    exercises: function () {
      var xs = G.exercises || []; if (!xs.length) return "";
      return '<div class="grid-cards">' + xs.map(function (x) {
        return '<div class="mini"><span class="pill ' + (x.level === "hard" ? "high" : x.level === "medium" ? "medium" : "core") + '" style="justify-self:start">' + esc(x.level || "") + "</span><h4>" + esc(x.title) + "</h4>" +
          '<div class="prose" style="font-size:.9rem">' + md(x.goal) + "</div>" + (x.files && x.files.length ? chips(x.files) : "") +
          (x.hints && x.hints.length ? '<details class="deeper"><summary>Hints</summary><div class="prose"><ul>' + x.hints.map(function (hh) { return "<li>" + inline(hh) + "</li>"; }).join("") + "</ul></div></details>" : "") +
          (x.done_when ? '<p class="try"><b>Done when:</b> ' + inline(x.done_when) + "</p>" : "") + "</div>";
      }).join("") + "</div>";
    }
  };
  function renderView(v) {
    var fn = VIEWS[v && v.view];
    var inner = fn ? fn(v) : "";
    return inner ? '<section class="view">' + inner + "</section>" : "";
  }

  // ------------------------------------------------------------------ lesson
  function checkpointHTML(l) {
    var cp = l.checkpoint; if (!cp || !cp.choices) return "";
    var ans = state.quiz[l.id];
    var answered = typeof ans === "number";
    return '<div class="checkpoint" data-cp="' + esc(l.id) + '"><span class="eyebrow">Checkpoint</span><p class="q">' + inline(cp.q) + '</p><div class="opts">' +
      cp.choices.map(function (c, i) {
        var cls = answered ? (i === cp.answer ? " right" : (i === ans ? " wrong" : "")) : "";
        return '<button type="button" class="opt' + cls + '" data-opt="' + i + '"' + (answered ? " disabled" : "") + '><span class="k">' + "ABCDEFG".charAt(i) + "</span><span>" + inline(c) + "</span></button>";
      }).join("") + "</div>" +
      (answered ? '<p class="why">' + (ans === cp.answer ? "<strong>Right.</strong> " : "<strong>Not quite.</strong> ") + inline(cp.explain || "") +
        ' <button type="button" class="btn ghost" data-retry="' + esc(l.id) + '" style="height:28px">Try again</button></p>' : "") + "</div>";
  }
  function lessonHTML(l, h1) {
    var R = currentRoute(), scale = R ? R.bg.scale : 1;
    var tag = h1 ? "h1" : "h2";
    return '<div class="lesson-head">' + exitTab(l.chapter) + "<" + tag + ' id="l-' + esc(l.id) + '">' + esc(l.title) + "</" + tag + '><div class="meta">' +
      '<span class="pill">' + fmtMin(Math.max(1, Math.round((l.minutes || 5) * scale))) + "</span>" +
      '<span class="pill ' + (l.tier === "core" ? "core" : "") + '">' + esc(l.tier || "") + "</span>" +
      (l["for"] && l["for"].indexOf("new") >= 0 ? '<span class="pill">for newcomers</span>' : "") +
      (isDone(l.id) ? '<span class="pill core">done</span>' : "") + "</div></div>" +
      '<div class="tldr"><span class="label">In short</span><p>' + inline(l.summary) + "</p></div>" +
      '<div class="prose">' + md(l.body) + "</div>" +
      (l.diagram ? mermaidBlock(l.diagram) : "") +
      (l.show || []).map(renderView).join("") +
      (l.deeper ? '<details class="deeper"><summary>Go deeper</summary><div class="prose">' + md(l.deeper) + "</div></details>" : "") +
      checkpointHTML(l);
  }

  // ------------------------------------------------------------------ file card
  function fileCard(path, compact) {
    var c = CARDS[path] || {}, f = FBY[path] || {};
    var h = '<div class="file-card"><div><span class="eyebrow">' + esc(c.area || f.l || "file") + (f.n ? " · " + fmtNum(f.n) + " lines" : "") + '</span><div class="path">' + esc(path) + "</div></div>";
    var rows = [];
    if (c.role) rows.push(["Role", "<p>" + inline(c.role) + "</p>"]);
    if (c.summary) rows.push(["What it does", '<div class="prose">' + md(c.summary) + "</div>"]);
    if (c.symbols && c.symbols.length) rows.push(["Key parts", '<div class="list-rows" style="border-top:0">' + c.symbols.map(function (s) {
      return '<div class="list-row" style="grid-template-columns:minmax(0,1fr)"><div><span class="mono" style="color:var(--ink);font-size:.86rem">' + esc(s.name) + "</span> " + inline(s.at || "") + '<p class="muted">' + inline(s.does || "") + "</p></div></div>";
    }).join("") + "</div>"]);
    if (c.read_when) rows.push(["Open it when", "<p>" + inline(c.read_when) + "</p>"]);
    if (c.gotchas) rows.push(["Watch out", '<div class="prose">' + md(c.gotchas) + "</div>"]);
    if (c.complexity) rows.push(["Complexity", '<span class="meter">' + [1, 2, 3, 4, 5].map(function (i) { return '<i class="' + (i <= c.complexity ? "on" : "") + '"></i>'; }).join("") + "</span>"]);
    if (f.i && f.i.length) rows.push(["Depends on", chips(f.i)]);
    if (f.u && f.u.length) rows.push(["Used by", chips(f.u)]);
    if (f.c) rows.push(["History", "<p>Changed in " + f.c + " commit" + (f.c === 1 ? "" : "s") + ".</p>"]);
    var sh = SESS && SESS.files && SESS.files[path];
    if (sh) rows.push(["Built with Claude", '<div style="display:grid;gap:10px"><p class="muted">' + sh.edits + " edit" + (sh.edits === 1 ? "" : "s") + " in Claude Code sessions, " + esc(sh.first.slice(0, 10)) + " to " + esc(sh.last.slice(0, 10)) + ".</p>" +
      sh.events.slice(0, 4).map(function (e) {
        return '<div class="history-item"><span class="subtle mono" style="font-size:.72rem">' + esc(e.at) + " · " + esc(e.tool) + "</span>" + (e.prompt ? "<q>" + esc(e.prompt) + "</q>" : "") + (e.why ? '<span class="muted">' + esc(e.why) + "</span>" : "") + "</div>";
      }).join("") + "</div>"]);
    if (SRC[path]) rows.push(["Source", '<button class="btn" type="button" data-source="' + esc(path) + '">Read the whole file</button>']);
    if (!rows.length) rows.push(["", '<p class="empty">The guide has no notes on this file yet. ' + (SRC[path] ? "" : "") + "</p>"]);
    h += '<div class="rows">' + rows.map(function (r) {
      return '<div class="row" style="padding-block:16px"><div class="label">' + r[0] + '</div><div class="content">' + r[1] + "</div></div>";
    }).join("") + "</div></div>";
    return compact ? '<div class="schematic" style="background-image:none;padding:20px 22px">' + h + "</div>" : h;
  }

  // ------------------------------------------------------------------ screens
  function numbersHTML() {
    var items = (G.numbers && G.numbers.length) ? G.numbers.map(function (n) { return [n.value, n.label]; }) : [];
    var v = G.verification || {}, sm = S.summary || {};
    if (!items.length) {
      if (sm.lines) items.push([fmtNum(sm.lines), "lines of code"]);
      if (sm.source_files) items.push([fmtNum(sm.source_files), "source files"]);
      if (S.git && S.git.commits) items.push([fmtNum(S.git.commits), "commits"]);
    }
    if (v.citations) items.push([fmtNum(v.verified) + "/" + fmtNum(v.citations), "claims checked against the code"]);
    return '<div class="numbers">' + items.slice(0, 5).map(function (n) { return '<div class="num"><b>' + esc(n[0]) + "</b><span>" + esc(n[1]) + "</span></div>"; }).join("") + "</div>";
  }

  function viewPlan() {
    var draft = Object.assign({ time: "d1", goal: "gist", bg: "know" }, state.route || {});
    function group(key, opts) {
      return '<div class="choices" data-k="' + key + '">' + opts.map(function (o) {
        return '<button type="button" class="choice" data-v="' + o.id + '" aria-pressed="' + (draft[key] === o.id) + '"><b>' + esc(o.label) + "</b><span>" + esc(o.sub) + "</span></button>";
      }).join("") + "</div>";
    }
    main.innerHTML = '<div class="wrap"><section class="hero"><span class="eyebrow">Onramp · your route through</span><h1>' + esc(P.name || S.name || "this project") + "</h1>" +
      '<p class="one">' + inline(P.one_liner) + "</p>" + numbersHTML() + "</section>" +
      '<div class="rows">' +
      '<div class="row"><div class="label">How much time do you have?</div><div class="content">' + group("time", TIMES) + "</div></div>" +
      '<div class="row"><div class="label">What do you want to do?</div><div class="content">' + group("goal", GOALS) + "</div></div>" +
      '<div class="row"><div class="label">Your background</div><div class="content">' + group("bg", BGS) + "</div></div>" +
      '<div class="row"><div class="label">Your route<small>Recalculated as you choose</small></div><div class="content" id="preview"></div></div>' +
      (P.what || P.analogy ? '<div class="row"><div class="label">About this project</div><div class="content prose">' + md(P.what) + (P.analogy ? '<p class="muted"><strong>In one picture:</strong> ' + inline(P.analogy) + "</p>" : "") + "</div></div>" : "") +
      "</div>" + footer() + "</div>";
    function preview() {
      var R = buildRoute(draft);
      $("#preview").innerHTML = '<div class="preview"><div class="preview-head"><b>' + esc(R.time.label) + " · " + R.stops.length + " stops</b>" +
        '<span class="pill">' + fmtMin(R.mins) + " of reading and doing</span><span class=\"pill\">" + esc(R.goal.label) + "</span></div>" +
        '<div class="days">' + R.segs.map(function (sg) {
          return '<div class="day-line"><span class="d">' + esc(sg.name) + '</span><span class="t">' + esc(sg.title) + '</span><span class="m">' + sg.stops.length + " stops · " + fmtMin(sg.mins) + "</span></div>";
        }).join("") + '</div><div><button class="sign" type="button" id="start">' + (state.route ? "Update my route" : "Start the route") + ' <span class="arrow">→</span></button></div></div>';
      $("#start").onclick = function () { state.route = draft; save(); location.hash = "#route"; };
    }
    $$(".choices", main).forEach(function (grp) {
      grp.addEventListener("click", function (e) {
        var b = e.target.closest(".choice"); if (!b) return;
        draft[grp.dataset.k] = b.dataset.v;
        $$(".choice", grp).forEach(function (x) { x.setAttribute("aria-pressed", String(x === b)); });
        preview();
      });
    });
    preview();
  }

  var roadDrawn = false;
  function viewRoute() {
    var R = currentRoute();
    if (!R) { viewPlan(); return; }
    var all = R.stops, done = all.filter(function (s) { return isDone(s.l.id); }).length;
    var here = all.filter(function (s) { return !isDone(s.l.id); })[0];
    var left = all.filter(function (s) { return !isDone(s.l.id); }).reduce(function (a, s) { return a + s.mins; }, 0);
    var pct = all.length ? Math.round(100 * done / all.length) : 0;
    var k = 0, items = "";
    R.segs.forEach(function (sg) {
      items += '<li class="rest"><div class="sign"><small>' + esc(sg.name.toUpperCase()) + "</small><span>" + esc(sg.title) + "</span><em>" + sg.stops.length + " stops · " + fmtMin(sg.mins) + "</em></div></li>";
      sg.stops.forEach(function (s) {
        var l = s.l, isHere = here && here.l.id === l.id, dx = Math.round(Math.sin(k * 0.95) * 38);
        items += '<li class="stop' + (k % 2 ? " left" : "") + (isDone(l.id) ? " done" : "") + (isHere ? " here" : "") + '" style="--dx:' + dx + 'px">' +
          '<span class="marker">' + (isHere ? '<span class="here-tag">YOU ARE HERE</span>' : "") + "</span>" +
          '<button type="button" class="card" data-go="#stop-' + esc(l.id) + '">' + exitTab(l.chapter) + "<h3>" + esc(l.title) + "</h3><p>" + esc(stripCites(l.summary)) + '</p><div class="card-foot">' + (isHere ? '<span class="pill here-pill">you are here</span>' : "") + '<span class="pill">' + fmtMin(s.mins) + "</span>" +
          (l.tier === "core" ? '<span class="pill core">core</span>' : "") + (l.checkpoint ? '<span class="pill">checkpoint</span>' : "") + (isDone(l.id) ? '<span class="pill core">done</span>' : "") + "</div></button></li>";
        k++;
      });
    });
    var score = quizScore(all);
    var finish = done === all.length && all.length
      ? '<div class="finish"><span class="eyebrow">Route complete</span><h2>You know your way around ' + esc(P.name || "") + '.</h2><p class="muted">' + esc(R.time.label) + " route · " + all.length + " stops · " + fmtMin(R.mins) +
        (score[1] ? " · " + score[0] + "/" + score[1] + " checkpoints right" : "") + '</p><p class="subtle mono" style="font-size:.74rem">Generated with Onramp · github.com/SanyamWadhwa07/onramp</p></div>'
      : '<span class="sign" style="cursor:default">Destination · ' + esc(P.name || "") + "</span>";
    main.innerHTML = '<div class="wrap"><div class="route-head"><div><span class="eyebrow">Your route</span><h2>' + esc(R.time.label) + " through " + esc(P.name || "the project") + "</h2>" +
      '<div class="meta"><span class="pill">' + esc(R.goal.label) + '</span><span class="pill">' + esc(R.bg.label) + '</span><span class="pill">' + all.length + " stops · " + fmtMin(R.mins) + "</span></div></div>" +
      '<div class="progress"><div class="bar"><i style="width:' + pct + '%"></i></div><small>' + done + " of " + all.length + " stops done" + (left ? " · " + fmtMin(left) + " to go" : "") + "</small>" +
      '<div style="display:flex;gap:8px;flex-wrap:wrap">' + (here ? '<a class="sign" href="#stop-' + esc(here.l.id) + '">' + (done ? "Continue" : "Start driving") + ' <span class="arrow">→</span></a>' : "") +
      '<a class="btn ghost" href="#plan">Change route</a></div></div></div>' +
      '<div class="road-wrap" id="road"><svg class="road-svg" id="road-svg" aria-hidden="true"></svg>' +
      '<div class="endpoint"><span class="sign" style="cursor:default">Onramp · start here</span></div>' +
      '<ol class="stops">' + items + "</ol>" +
      '<div class="endpoint" style="margin-top:22px">' + finish + "</div></div>" + footer() + "</div>";
    requestAnimationFrame(drawRoad);
  }
  function stripCites(s) { return String(s || "").replace(CITE_RE, function (m, p) { return base(p); }).replace(/`/g, ""); }
  function quizScore(stops) {
    var right = 0, asked = 0;
    stops.forEach(function (s) { var cp = s.l.checkpoint; if (cp && typeof state.quiz[s.l.id] === "number") { asked++; if (state.quiz[s.l.id] === cp.answer) right++; } });
    return [right, asked];
  }
  function drawRoad() {
    var wrap = $("#road"), svg = $("#road-svg");
    if (!wrap || !svg) return;
    var box = wrap.getBoundingClientRect();
    var narrow = window.matchMedia("(max-width: 760px)").matches;
    var firstMarker = $(".stop .marker", wrap), mx = null;
    if (firstMarker) { var fr = firstMarker.getBoundingClientRect(); mx = fr.left + fr.width / 2 - box.left; }
    var pts = $$(".endpoint .sign, .rest .sign, .stop .marker", wrap).map(function (el) {
      var r = el.getBoundingClientRect(), li = el.closest(".stop");
      var x = r.left + r.width / 2 - box.left;
      if (narrow && !li && mx !== null) x = mx;
      return { x: x, y: r.top + r.height / 2 - box.top, done: li ? li.classList.contains("done") : null, el: el };
    }).sort(function (a, b) { return a.y - b.y; });
    var prevDone = true;
    pts.forEach(function (p) { if (p.done === null) p.done = prevDone; prevDone = p.done; });
    svg.setAttribute("width", box.width); svg.setAttribute("height", box.height);
    svg.setAttribute("viewBox", "0 0 " + box.width + " " + box.height);
    function seg(i) {
      var p0 = pts[i - 1] || pts[i], p1 = pts[i], p2 = pts[i + 1], p3 = pts[i + 2] || p2;
      return " C" + (p1.x + (p2.x - p0.x) / 6).toFixed(1) + "," + (p1.y + (p2.y - p0.y) / 6).toFixed(1) + " " + (p2.x - (p3.x - p1.x) / 6).toFixed(1) + "," + (p2.y - (p3.y - p1.y) / 6).toFixed(1) + " " + p2.x.toFixed(1) + "," + p2.y.toFixed(1);
    }
    if (pts.length < 2) { svg.innerHTML = ""; return; }
    var full = "M" + pts[0].x.toFixed(1) + "," + pts[0].y.toFixed(1), lanes = "";
    for (var i = 0; i < pts.length - 1; i++) {
      var s = seg(i);
      full += s;
      lanes += '<path class="lane' + (pts[i].done && pts[i + 1].done ? " done" : "") + '" d="M' + pts[i].x.toFixed(1) + "," + pts[i].y.toFixed(1) + s + '"/>';
    }
    svg.innerHTML = '<path class="edge" d="' + full + '"/><path class="tar" d="' + full + '"/>' + lanes;
    if (!roadDrawn && !window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      roadDrawn = true;
      $$("path", svg).forEach(function (p) {
        var len = p.getTotalLength();
        p.style.strokeDasharray = p.classList.contains("lane") && !p.classList.contains("done") ? "" : len;
        if (p.style.strokeDasharray) {
          p.style.strokeDashoffset = len;
          p.getBoundingClientRect();
          p.style.transition = "stroke-dashoffset 1.1s ease";
          p.style.strokeDashoffset = 0;
          p.addEventListener("transitionend", function () { p.style.strokeDasharray = ""; p.style.strokeDashoffset = ""; }, { once: true });
        }
      });
    }
  }

  function viewStop(id) {
    var l = BYID[id];
    if (!l) { main.innerHTML = '<div class="wrap"><h2>That stop is not in this guide.</h2><p><a href="#route">Back to the route</a></p></div>'; return; }
    var R = currentRoute(), seq, segIdx = -1;
    if (R && R.stops.some(function (s) { return s.l.id === id; })) {
      seq = R.stops.map(function (s) { return s.l; });
      segIdx = R.stops.filter(function (s) { return s.l.id === id; })[0].seg;
    } else {
      seq = LESSONS.slice().sort(function (a, b) { return (CH[a.chapter] || {}).n - (CH[b.chapter] || {}).n || a._i - b._i; });
    }
    var pos = seq.indexOf(l), prev = seq[pos - 1], next = seq[pos + 1];
    var railList = segIdx >= 0 ? R.segs[segIdx].stops.map(function (s) { return s.l; }) : seq.filter(function (x) { return x.chapter === l.chapter; });
    var railHead = segIdx >= 0 ? esc(R.segs[segIdx].name) + " · " + esc(R.segs[segIdx].title) : esc((CH[l.chapter] || {}).title || "");
    main.innerHTML = '<div class="wrap"><div class="lesson-grid"><aside class="rail"><span class="eyebrow">' + railHead + "</span><ol>" +
      railList.map(function (x) {
        return '<li><a href="#stop-' + esc(x.id) + '" class="' + (x.id === id ? "on " : "") + (isDone(x.id) ? "done" : "") + '"><span class="ck"></span><span>' + esc(x.title) + "</span></a></li>";
      }).join("") + '</ol><a class="btn ghost" href="#route">← Back to the route</a></aside>' +
      '<article class="lesson">' + lessonHTML(l, true) +
      '<nav class="lesson-nav">' + (prev ? '<a class="btn ghost" href="#stop-' + esc(prev.id) + '">← ' + esc(prev.title) + "</a>" : "<span></span>") +
      (isDone(id)
        ? '<span style="display:flex;gap:8px;flex-wrap:wrap"><button class="btn ghost" type="button" data-undone="' + esc(id) + '">Mark as not done</button>' + (next ? '<a class="sign" href="#stop-' + esc(next.id) + '">Next stop <span class="arrow">→</span></a>' : '<a class="sign" href="#route">Back to the route</a>') + "</span>"
        : '<button class="sign" type="button" data-done="' + esc(id) + '" data-next="' + esc(next ? next.id : "") + '">' + (next ? "Done, next stop" : "Done, finish the route") + ' <span class="arrow">→</span></button>') +
      "</nav></article></div>" + footer() + "</div>";
  }

  function viewMap() {
    var h = '<div class="wrap"><div class="hero"><span class="eyebrow">The map</span><h1>How ' + esc(P.name || "it") + " fits together</h1></div><div class=\"rows\">";
    if (G.architecture) h += '<div class="row"><div class="label">Architecture<small>Written by the guide, checked against the code</small></div><div class="content view">' + VIEWS.architecture() + "</div></div>";
    h += '<div class="row"><div class="label">Module dependencies<small>Computed from imports</small></div><div class="content view">' + VIEWS.depmap() + "</div></div>";
    if ((S.languages || []).length) h += '<div class="row"><div class="label">Languages</div><div class="content view">' + VIEWS.languages() + "</div></div>";
    if ((S.entrypoints || []).length) h += '<div class="row"><div class="label">Entry points<small>Where execution starts</small></div><div class="content"><div class="list-rows" style="border-top:0">' +
      S.entrypoints.slice(0, 14).map(function (e) { return '<div class="list-row"><b class="mono" style="font-family:var(--font-mono);font-size:.84rem;word-break:break-all"><a href="#files/' + esc(e.path) + '">' + esc(e.path) + '</a></b><div class="muted">' + esc(e.why) + "</div></div>"; }).join("") + "</div></div></div>";
    if (S.git && S.git.timeline && S.git.timeline.length) h += '<div class="row"><div class="label">History</div><div class="content view">' + VIEWS.timeline() + "</div></div>";
    if ((S.env_vars || []).length) h += '<div class="row"><div class="label">Environment<small>Variables the code reads</small></div><div class="content"><div class="chips">' +
      S.env_vars.map(function (e) { return '<span class="pill" title="' + esc((e.files || []).join(", ")) + '">' + esc(e.name) + "</span>"; }).join("") + "</div></div></div>";
    main.innerHTML = h + "</div>" + footer() + "</div>";
  }

  var filesOnlyNoted = null;
  function treeHTML(filter) {
    var q = (filter || "").toLowerCase().trim();
    var list = FILES.filter(function (f) { return f.k !== "lock" && (!filesOnlyNoted || CARDS[f.p]) && (!q || f.p.toLowerCase().indexOf(q) >= 0); });
    if (!list.length) return '<p class="empty" style="padding:8px 12px">No files match.</p>';
    if (q) return list.slice(0, 400).map(fileLink).join("");
    var root = {};
    list.forEach(function (f) {
      var parts = f.p.split("/"), node = root;
      for (var i = 0; i < parts.length - 1; i++) { node[parts[i] + "/"] = node[parts[i] + "/"] || {}; node = node[parts[i] + "/"]; }
      node[parts[parts.length - 1]] = f;
    });
    function render(node, depth) {
      return Object.keys(node).sort(function (a, b) { var da = a.slice(-1) === "/", db = b.slice(-1) === "/"; return da === db ? a.localeCompare(b) : (da ? -1 : 1); }).map(function (k) {
        if (k.slice(-1) === "/") return "<details" + (depth < 1 || filesOnlyNoted ? " open" : "") + "><summary>" + esc(k) + '</summary><div class="kids">' + render(node[k], depth + 1) + "</div></details>";
        return fileLink(node[k], true);
      }).join("");
    }
    return render(root, 0);
  }
  function fileLink(f, short) {
    return '<a href="#files/' + esc(f.p) + '" data-path="' + esc(f.p) + '" class="' + (CARDS[f.p] ? "noted" : "") + '"><span>' + esc(short ? base(f.p) : f.p) + '</span><span class="n">' + (f.n ? fmtNum(f.n) : "") + "</span></a>";
  }
  function viewFiles(path) {
    if (filesOnlyNoted === null) filesOnlyNoted = Object.keys(CARDS).length >= 8;
    var existing = $("#tree");
    if (!existing) {
      main.innerHTML = '<div class="wrap"><div class="files-grid"><div class="tree-pane"><div class="tree-tools"><input type="search" id="tree-q" placeholder="Filter files" aria-label="Filter files">' +
        '<label><input type="checkbox" id="tree-noted"' + (filesOnlyNoted ? " checked" : "") + "> with notes</label></div>" +
        '<nav class="tree" id="tree" aria-label="Files">' + treeHTML("") + '</nav><span class="subtle" style="font-size:.78rem">● files the guide explains · ' + fmtNum(FILES.length) + " files scanned</span></div>" +
        '<section id="file-pane"></section></div>' + footer() + "</div>";
      $("#tree-q").addEventListener("input", function () { $("#tree").innerHTML = treeHTML(this.value); markTree(); });
      $("#tree-noted").addEventListener("change", function () { filesOnlyNoted = this.checked; $("#tree").innerHTML = treeHTML($("#tree-q").value); markTree(); });
    }
    var pane = $("#file-pane");
    if (path) {
      pane.innerHTML = fileCard(path, false);
    } else {
      var groups = {};
      (G.files || []).forEach(function (c) { (groups[c.area || "Other"] = groups[c.area || "Other"] || []).push(c); });
      pane.innerHTML = '<div style="display:grid;gap:22px"><div><span class="eyebrow">File by file</span><h2>Pick a file to see what it does</h2><p class="muted" style="margin-top:8px">The guide explains ' + Object.keys(CARDS).length + " of " + fmtNum(FILES.length) + " files: the ones you need to open. Each card shows what the file depends on and what uses it, computed from the imports.</p></div>" +
        Object.keys(groups).map(function (g) { return '<div class="view"><span class="view-title">' + esc(g) + "</span>" + VIEWS.files({ paths: groups[g].map(function (c) { return c.path; }) }) + "</div>"; }).join("") + "</div>";
    }
    markTree(path);
    if (path && existing) pane.scrollIntoView({ block: "start" });
  }
  function markTree(path) {
    path = path || decodeURIComponent(location.hash.slice(7));
    $$("#tree a").forEach(function (a) { a.classList.toggle("on", a.dataset.path === path); });
  }

  function viewGuide() {
    var toc = "", body = "";
    CHAPTERS.forEach(function (c, i) {
      var ls = LESSONS.filter(function (l) { return l.chapter === c[0]; });
      if (!ls.length) return;
      toc += '<a href="#guide" data-jump="ch-' + c[0] + '"><span>' + pad(i + 1) + "</span><span>" + esc(c[1]) + "</span></a>";
      body += '<section class="chapter" id="ch-' + c[0] + '">' + ls.map(function (l) { return '<article class="lesson">' + lessonHTML(l, false) + "</article>"; }).join("") + "</section>";
    });
    main.innerHTML = '<div class="wrap"><div class="hero"><span class="eyebrow">The full guide</span><h1>' + esc(P.name || "") + ", start to finish</h1>" +
      '<p class="one">Every stop in order, for reading straight through. ' + LESSONS.length + " stops, " + fmtMin(LESSONS.reduce(function (a, l) { return a + (l.minutes || 0); }, 0)) + ".</p></div>" +
      '<div class="guide-grid"><nav class="toc" aria-label="Chapters">' + toc + "</nav><div>" + body + "</div></div>" + footer() + "</div>";
  }

  // ------------------------------------------------------------------ code peek
  var peek = $("#peek"), scrim = $("#scrim"), lastFocus = null;
  var HL_LANG = { py: "python", js: "javascript", jsx: "javascript", mjs: "javascript", cjs: "javascript", ts: "typescript", tsx: "typescript", go: "go", rs: "rust", java: "java", kt: "kotlin", rb: "ruby", php: "php", c: "c", h: "c", cc: "cpp", cpp: "cpp", hpp: "cpp", cs: "csharp", swift: "swift", sh: "bash", bash: "bash", json: "json", yml: "yaml", yaml: "yaml", toml: "ini", ini: "ini", md: "markdown", html: "xml", vue: "xml", svelte: "xml", xml: "xml", css: "css", scss: "scss", sql: "sql", dockerfile: "dockerfile" };
  var hljsP = null;
  function langOf(path) { var b = base(path).toLowerCase(); if (b.indexOf("dockerfile") === 0) return "dockerfile"; return HL_LANG[b.split(".").pop()] || null; }
  function splitLines(html) {
    var out = [], open = [], cur = "", re = /(<span[^>]*>)|(<\/span>)|(\n)|([^<\n]+)|(<)/g, m;
    while ((m = re.exec(html))) {
      if (m[1]) { open.push(m[1]); cur += m[1]; }
      else if (m[2]) { open.pop(); cur += m[2]; }
      else if (m[3]) { cur += new Array(open.length + 1).join("</span>"); out.push(cur); cur = open.join(""); }
      else cur += m[4] || m[5];
    }
    out.push(cur + new Array(open.length + 1).join("</span>"));
    return out;
  }
  function codeHTML(code, from, hs, he, path) {
    var lang = langOf(path), lines;
    if (window.hljs && lang && window.hljs.getLanguage(lang)) {
      try { lines = splitLines(window.hljs.highlight(code, { language: lang, ignoreIllegals: true }).value); } catch (e) { lines = null; }
    }
    if (!lines) lines = code.split("\n").map(esc);
    return '<div class="code">' + lines.map(function (ln, i) {
      var n = from + i;
      return '<div class="ln' + (n >= hs && n <= he ? " hl" : "") + '" data-n="' + n + '"><span class="no">' + n + "</span><span>" + (ln || " ") + "</span></div>";
    }).join("") + "</div>";
  }
  var peekState = null;
  function showPeek(st) {
    peekState = st;
    var path = st.path;
    $("#peek-path").textContent = path;
    $("#peek-lines").textContent = st.label || "";
    var acts = "";
    if (st.kind === "snip" && SRC[path]) acts += '<button type="button" data-source="' + esc(path) + '">Whole file</button>';
    if (META.root) acts += '<a href="vscode://file/' + encodeURI(String(META.root).replace(/\\/g, "/") + "/" + path) + ":" + (st.hs || 1) + '">Open in editor</a>';
    if (META.github && META.commit) acts += '<a target="_blank" rel="noopener" href="' + esc(META.github + "/blob/" + META.commit + "/" + path + (st.hs ? "#L" + st.hs + (st.he && st.he !== st.hs ? "-L" + st.he : "") : "")) + '">GitHub</a>';
    if (CARDS[path] || FBY[path]) acts += '<a href="#files/' + esc(path) + '">File card</a>';
    $("#peek-actions").innerHTML = acts;
    var body = st.html || codeHTML(st.code, st.from, st.hs, st.he, path);
    $("#peek-body").innerHTML = body + (st.note ? '<div class="code-note">' + st.note + "</div>" : "");
    if (!peek.classList.contains("open")) lastFocus = document.activeElement;
    peek.classList.add("open"); peek.setAttribute("aria-hidden", "false"); scrim.hidden = false;
    var hl = $(".ln.hl", peek);
    if (hl) hl.scrollIntoView({ block: "center" }); else $("#peek-body").scrollTop = 0;
    $("#peek-close").focus({ preventScroll: true });
    if (!window.hljs && !st.html && langOf(path)) {
      hljsP = hljsP || loadScript(HLJS_URL).catch(function () { return null; });
      hljsP.then(function () { if (window.hljs && peekState === st) showPeek(st); });
    }
  }
  function openCite(key) {
    var s = SNIP[key];
    var m = key.match(/^(.*):(\d+)-(\d+)$/);
    if (!s || !m) {
      showPeek({ path: m ? m[1] : key, kind: "msg", html: '<p class="empty" style="padding:18px">This excerpt was not embedded in the guide.</p>' });
      return;
    }
    showPeek({ kind: "snip", path: s.path, code: s.code, from: s.from, hs: s.start, he: s.end,
      label: "lines " + s.start + (s.end !== s.start ? "–" + s.end : "") + " of " + fmtNum(s.total),
      note: "Read from the file when the guide was built. Highlighted lines are the ones cited." });
  }
  function openSource(path) {
    if (!SRC[path]) return;
    showPeek({ kind: "src", path: path, code: SRC[path], from: 1, hs: 0, he: -1, label: fmtNum(SRC[path].split("\n").length) + " lines" });
  }
  function openTrust() {
    var v = G.verification;
    var html = '<div class="prose" style="padding:22px;max-width:60ch">' + (v ? "<h3>" + fmtNum(v.verified) + " of " + fmtNum(v.citations) + " claims verified</h3>" +
      "<p>Every citation in this guide points at a file, a line range, and a short piece of text from those lines. Before the guide was built, <code>verify.py</code> opened each file and checked that the lines exist and that the quoted text is really there" +
      (v.commit ? ", at commit <code>" + esc(v.commit) + "</code>" : "") + (v.checked_at ? " on " + esc(v.checked_at.slice(0, 10)) : "") + ".</p>" +
      "<p>" + fmtNum(v.files_cited) + " files are cited. " + (v.auto_fixed ? fmtNum(v.auto_fixed) + " citations had drifted line numbers and were re-anchored automatically. " : "") + "A claim whose text could not be found in the code fails the check and has to be rewritten before the guide can be published.</p>" +
      "<p>The code you see when you click a citation is copied from the file itself, not written by the model.</p>"
      : "<h3>Not verified</h3><p>This guide was rendered without running <code>verify.py</code>, so its citations have not been checked.</p>") + "</div>";
    showPeek({ kind: "msg", path: "How this guide is checked", html: html, label: "" });
  }
  function closePeek() {
    if (!peek.classList.contains("open")) return;
    peek.classList.remove("open"); peek.setAttribute("aria-hidden", "true"); scrim.hidden = true; peekState = null;
    if (lastFocus && lastFocus.focus) lastFocus.focus({ preventScroll: true });
  }

  // ------------------------------------------------------------------ diagrams
  var mermaidP = null, mmId = 0;
  function themeVars() {
    var cs = getComputedStyle(document.documentElement);
    function v(n) { return cs.getPropertyValue(n).trim(); }
    return {
      background: v("--surface"), primaryColor: v("--surface"), primaryTextColor: v("--ink"), primaryBorderColor: v("--border-strong"),
      secondaryColor: v("--surface-2"), tertiaryColor: v("--bg"), lineColor: v("--muted"), textColor: v("--text"),
      clusterBkg: v("--surface-2"), clusterBorder: v("--border"), edgeLabelBackground: v("--surface"), mainBkg: v("--surface"),
      nodeBorder: v("--border-strong"), titleColor: v("--ink"), noteBkgColor: v("--surface-2"), noteTextColor: v("--ink"),
      actorBkg: v("--surface"), actorBorder: v("--border-strong"), actorTextColor: v("--ink"), signalColor: v("--muted"), signalTextColor: v("--text"),
      attributeBackgroundColorOdd: v("--surface"), attributeBackgroundColorEven: v("--surface-2"),
      fontFamily: '"Onest", system-ui, sans-serif', fontSize: "14px"
    };
  }
  function renderDiagrams(root) {
    var blocks = $$(".mermaid-block:not([data-done])", root);
    if (!blocks.length) return;
    mermaidP = mermaidP || loadScript(MERMAID_URL).then(function () { return window.mermaid; });
    mermaidP.then(function (m) {
      m.initialize({ startOnLoad: false, theme: "base", themeVariables: themeVars(), securityLevel: "strict", flowchart: { htmlLabels: true, curve: "basis" } });
      var chain = Promise.resolve();
      blocks.forEach(function (b) {
        chain = chain.then(function () {
          if (!document.body.contains(b)) return;
          var src = $("pre.src", b).textContent, id = "onramp-mm-" + (++mmId);
          return m.render(id, src).then(function (r) {
            $(".mermaid-out", b).innerHTML = r.svg; $("pre.src", b).hidden = true; b.dataset.done = "1";
          }).catch(function () {
            var stray = document.getElementById("d" + id); if (stray) stray.remove();
            $(".mermaid-out", b).innerHTML = '<p class="empty">This diagram could not be drawn. Its source:</p>'; b.dataset.done = "1";
          });
        });
      });
    }).catch(function () {
      blocks.forEach(function (b) { $(".mermaid-out", b).innerHTML = '<p class="empty">Diagrams need an internet connection to draw. Source:</p>'; b.dataset.done = "1"; });
    });
  }

  // ------------------------------------------------------------------ search
  var INDEX = null, sel = 0, results = [];
  function buildIndex() {
    var idx = [];
    LESSONS.forEach(function (l) { idx.push({ k: "stop", t: l.title, s: stripCites(l.summary), go: "#stop-" + l.id }); });
    Object.keys(CARDS).forEach(function (p) { idx.push({ k: "file", t: p, s: stripCites(CARDS[p].role || CARDS[p].summary || ""), go: "#files/" + p, w: 1 }); });
    FILES.forEach(function (f) { if (!CARDS[f.p] && f.k !== "lock" && f.k !== "asset") idx.push({ k: "file", t: f.p, s: f.l + " · " + fmtNum(f.n) + " lines", go: "#files/" + f.p, w: -1 }); });
    var cl = lessonFor(function (l) { return (l.show || []).some(function (v) { return v.view === "concepts"; }); }) || lessonFor(function (l) { return l.chapter === "concepts"; });
    (G.concepts || []).forEach(function (c) { idx.push({ k: "idea", t: c.term, s: stripCites(c.plain), go: cl ? "#stop-" + cl.id : "#guide" }); });
    var sl = lessonFor(function (l) { return l.chapter === "stack"; });
    (G.stack || []).forEach(function (s) { idx.push({ k: "stack", t: s.name, s: stripCites(s.role), go: sl ? "#stop-" + sl.id : "#guide" }); });
    (G.flows || []).forEach(function (f) { var fl = lessonFor(function (l) { return (l.show || []).some(function (v) { return v.view === "flow" && v.id === f.id; }); }); idx.push({ k: "flow", t: f.title, s: stripCites(f.trigger || f.summary), go: fl ? "#stop-" + fl.id : "#guide" }); });
    idx.forEach(function (it) { it.hay = (it.t + " " + it.s).toLowerCase(); });
    return idx;
  }
  function runSearch(q) {
    INDEX = INDEX || buildIndex();
    q = q.toLowerCase().trim();
    var words = q.split(/\s+/).filter(Boolean);
    results = (words.length ? INDEX.filter(function (it) { return words.every(function (w) { return it.hay.indexOf(w) >= 0; }); }) : INDEX.filter(function (it) { return it.k === "stop"; }))
      .map(function (it) { var t = it.t.toLowerCase(); return { it: it, sc: (q && t.indexOf(q) === 0 ? 6 : 0) + (q && t.indexOf(q) >= 0 ? 3 : 0) + (it.w || 0) + (it.k === "stop" ? 1 : 0) }; })
      .sort(function (a, b) { return b.sc - a.sc; }).slice(0, 40).map(function (r) { return r.it; });
    sel = 0; paintResults();
  }
  function paintResults() {
    $("#search-results").innerHTML = results.length ? results.map(function (r, i) {
      return '<li class="' + (i === sel ? "on" : "") + '" data-i="' + i + '"><span class="k">' + r.k + "</span><span><b>" + esc(r.t) + "</b><small>" + esc(r.s) + "</small></span></li>";
    }).join("") : '<li><span class="k"></span><span class="empty">Nothing matches.</span></li>';
    var on = $("#search-results li.on"); if (on) on.scrollIntoView({ block: "nearest" });
  }
  function openSearch() { $("#search").hidden = false; var i = $("#search-input"); i.value = ""; runSearch(""); i.focus(); }
  function closeSearch() { $("#search").hidden = true; }
  function pick(i) { var r = results[i]; if (!r) return; closeSearch(); location.hash = r.go; }

  // ------------------------------------------------------------------ router + events
  function setTab(t) { $$("#tabs a").forEach(function (a) { if (a.dataset.tab === t) a.setAttribute("aria-current", "page"); else a.removeAttribute("aria-current"); }); }
  var lastView = "";
  function route() {
    closePeek();
    var h = decodeURIComponent(location.hash.slice(1)), tab = "route", view;
    if (!h) { view = "route"; if (state.route) viewRoute(); else viewPlan(); }
    else if (h === "plan") { view = "plan"; viewPlan(); }
    else if (h === "route") { view = "route"; viewRoute(); }
    else if (h.indexOf("stop-") === 0) { view = h; viewStop(h.slice(5)); }
    else if (h === "map") { view = tab = "map"; viewMap(); }
    else if (h === "files" || h.indexOf("files/") === 0) { tab = "files"; view = "files"; if (lastView !== "files") main.innerHTML = ""; viewFiles(h.slice(6)); }
    else if (h === "guide") { view = tab = "guide"; viewGuide(); }
    else { view = "route"; viewRoute(); }
    setTab(tab);
    if (!(view === "files" && lastView === "files")) window.scrollTo(0, 0);
    lastView = view;
    renderDiagrams(main);
  }

  document.addEventListener("click", function (e) {
    var t = e.target, el;
    if ((el = t.closest("[data-cite]"))) { e.preventDefault(); openCite(el.dataset.cite); return; }
    if ((el = t.closest("[data-file]"))) { e.preventDefault(); location.hash = "#files/" + el.dataset.file; return; }
    if ((el = t.closest("[data-source]"))) { e.preventDefault(); openSource(el.dataset.source); return; }
    if ((el = t.closest("[data-go]"))) { location.hash = el.dataset.go; return; }
    if ((el = t.closest("[data-jump]"))) { e.preventDefault(); var target = document.getElementById(el.dataset.jump); if (target) target.scrollIntoView({ behavior: "smooth" }); return; }
    if ((el = t.closest("[data-done]"))) {
      if (!isDone(el.dataset.done)) state.done.push(el.dataset.done);
      save(); location.hash = el.dataset.next ? "#stop-" + el.dataset.next : "#route"; return;
    }
    if ((el = t.closest("[data-undone]"))) { state.done = state.done.filter(function (x) { return x !== el.dataset.undone; }); save(); route(); return; }
    if ((el = t.closest(".checkpoint .opt"))) {
      var box = el.closest(".checkpoint"), id = box.dataset.cp;
      state.quiz[id] = +el.dataset.opt; save();
      box.outerHTML = checkpointHTML(BYID[id]); return;
    }
    if ((el = t.closest("[data-retry]"))) {
      var cpBox = el.closest(".checkpoint"); delete state.quiz[el.dataset.retry]; save();
      cpBox.outerHTML = checkpointHTML(BYID[el.dataset.retry]); return;
    }
    if ((el = t.closest("[data-flow-step]"))) {
      var wrap = el.closest(".view-flow"), f = FLOWS[wrap.dataset.flow], i = +el.dataset.flowStep;
      var steps = $$(".step", wrap);
      steps.forEach(function (s, j) { s.classList.toggle("active", j === i); });
      var st = f.steps[i];
      el.dataset.flowStep = String((i + 1) % steps.length);
      el.textContent = i + 1 < steps.length ? "Next step (" + (i + 2) + "/" + steps.length + ")" : "Start over";
      var m = String(st.at || "").match(/\[\[([^\[\]|:\n]+?):(\d+)(?:-(\d+))?/);
      if (m) openCite(m[1].trim() + ":" + m[2] + "-" + (m[3] || m[2]));
      return;
    }
    if (t.closest("#search-results li")) { pick(+t.closest("li").dataset.i); return; }
    if (t === $("#search")) closeSearch();
  });
  $("#peek-close").addEventListener("click", closePeek);
  scrim.addEventListener("click", closePeek);
  $("#trust").addEventListener("click", openTrust);
  $("#search-btn").addEventListener("click", openSearch);
  $("#search-input").addEventListener("input", function () { runSearch(this.value); });
  $("#search-input").addEventListener("keydown", function (e) {
    if (e.key === "ArrowDown") { sel = Math.min(results.length - 1, sel + 1); paintResults(); e.preventDefault(); }
    else if (e.key === "ArrowUp") { sel = Math.max(0, sel - 1); paintResults(); e.preventDefault(); }
    else if (e.key === "Enter") { pick(sel); e.preventDefault(); }
  });
  document.addEventListener("keydown", function (e) {
    var typing = /INPUT|TEXTAREA|SELECT/.test((document.activeElement || {}).tagName || "");
    if ((e.key === "k" && (e.ctrlKey || e.metaKey)) || (e.key === "/" && !typing)) { e.preventDefault(); openSearch(); }
    else if (e.key === "Escape") { if (!$("#search").hidden) closeSearch(); else closePeek(); }
  });
  $("#theme-btn").addEventListener("click", function () {
    var cur = document.documentElement.getAttribute("data-theme") || (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light");
    var next = cur === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem("onramp:theme", next); } catch (err) { /* ignore */ }
    if ($(".mermaid-block", main)) route();
  });
  var rt = null;
  window.addEventListener("resize", function () { clearTimeout(rt); rt = setTimeout(function () { if ($("#road")) drawRoad(); }, 120); });
  window.addEventListener("hashchange", route);
  if (document.fonts && document.fonts.ready) document.fonts.ready.then(function () { if ($("#road")) drawRoad(); });

  $("#brand-project").textContent = P.name || S.name || "Guide";
  trustBadge();
  route();
})();
