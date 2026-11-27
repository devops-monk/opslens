/* opslens explorer: a browser port of the CLI's catalog search (src/opslens/catalog/*.py).
   Data comes from /data/*.json, exported from the same shipped catalogs. All text is inserted with textContent. */
(() => {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const out = $("#out"), status = $("#status"), input = $("#q");
  let cfg, tables, pipes, tIndex, pIndex, mode = "all";

  const stem = (w) => {
    w = w.toLowerCase();
    if (w.length <= 3 || !w.endsWith("s") || /(ss|us|is)$/.test(w)) return w;
    if (w.endsWith("ies") && w.length > 4) return w.slice(0, -3) + "y";
    if (/(sses|ches|shes|xes|zes)$/.test(w)) return w.slice(0, -2);
    return w.slice(0, -1);
  };
  const tokens = (t) => (t || "").split(/[^a-zA-Z0-9]+/).filter(Boolean).map(stem);
  const set = (a) => new Set(a);
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };

  async function load() {
    status.textContent = "Loading catalogs…";
    const get = (f) => fetch(`../data/${f}`).then((r) => { if (!r.ok) throw new Error(f); return r.json(); });
    [cfg, tables, pipes] = await Promise.all([get("config.json"), get("tables.json"), get("pipelines.json")]);
    cfg.stop = set(cfg.stopwords);
    for (const k of ["write_words", "read_words", "destructive"]) cfg[k] = set(cfg[k]);
    tIndex = tables.map((t) => {
      const short = t.n.startsWith(t.p + "_") ? t.n.slice(t.p.length + 1) : t.n;
      return { t, ntok: set(tokens(short)), svc: set([...tokens(t.s), t.p]),
               desc: set(tokens(t.d).filter((w) => !cfg.stop.has(w))), cols: set(t.c.flatMap((c) => tokens(c[0]))) };
    });
    pIndex = pipes.map((p) => ({ p, ntok: set(tokens(p.s)), mod: set([p.m, ...tokens(p.m)]),
      desc: set(tokens(`${p.t} ${p.d}`).filter((w) => !cfg.stop.has(w))), params: set(p.p.flatMap((x) => tokens(x.n))) }));
    status.textContent = `${tables.length} tables · ${pipes.length} pipelines`;
  }

  function expand(words, extra) {
    const q = new Map();
    for (const w of words) {
      q.set(w, Math.max(q.get(w) || 0, 1));
      for (const s of [...(cfg.synonyms[w] || []), ...((extra && extra[w]) || [])]) { const k = stem(s); q.set(k, Math.max(q.get(k) || 0, 0.7)); }
    }
    return q;
  }

  function findTables(text, k = 8) {
    const words = tokens(text).filter((w) => !cfg.stop.has(w));
    const q = expand(words);
    const wantsMetric = ["metric", "cpu", "utilization", "memory", "idle"].some((w) => q.has(w));
    const wantsCost = q.has("cost");
    const scored = [];
    for (const x of tIndex) {
      let score = 0; const why = [];
      for (const [w, wt] of q) {
        if (x.ntok.has(w)) { score += 6 * wt; why.push(w); }
        else if (x.svc.has(w)) score += 3 * wt;
        else if (x.desc.has(w)) score += 1.5 * wt;
        else if (x.cols.has(w)) score += 0.8 * wt;
      }
      if (score <= 0) continue;
      score -= 0.7 * [...x.ntok].filter((w) => !q.has(w)).length;
      if (x.ntok.has("metric") && !wantsMetric) score -= 4;
      if (x.t.ce && !wantsCost) score -= 4;
      scored.push([score, x.t]);
    }
    scored.sort((a, b) => b[0] - a[0] || (a[1].n < b[1].n ? -1 : 1));
    return scored.slice(0, k).map((s) => s[1]);
  }

  function findPipes(text, k = 6) {
    const words = tokens(text).filter((w) => !cfg.stop.has(w) || cfg.write_words.has(w));
    const q = expand(words, cfg.verbs);
    const intent = set(words.filter((w) => cfg.write_words.has(w) || cfg.read_words.has(w)).flatMap((w) => [w, ...(cfg.verbs[w] || [])]).map(stem));
    const mentionedDestructive = [...intent].some((w) => cfg.destructive.has(w));
    const wantsWrite = words.some((w) => cfg.write_words.has(w));
    const scored = [];
    for (const x of pIndex) {
      let score = 0;
      for (const [w, wt] of q) {
        if (x.ntok.has(w)) score += 6 * wt;
        else if (x.mod.has(w)) score += wt === 1 ? 8 : 3 * wt;
        else if (x.desc.has(w)) score += 1.5 * wt;
        else if (x.params.has(w)) score += 0.5 * wt;
      }
      if (score <= 0) continue;
      const verb = x.p.s.split("_")[0];
      if (intent.has(verb)) score += 6; else if (cfg.destructive.has(verb) && !mentionedDestructive) score -= 5;
      if (x.p.rec) score += 1;
      if (wantsWrite && x.p.k === "write") score += 1;
      if ((x.p.m === "aws_thrifty" || x.p.m === "aws_tags") && !["thrifty", "tags", "tag", "detect", "correct"].some((w) => q.has(w))) score -= 3;
      score -= 0.1 * Math.max(x.ntok.size - 3, 0);
      scored.push([score, x.p]);
    }
    scored.sort((a, b) => b[0] - a[0] || (a[1].n < b[1].n ? -1 : 1));
    return scored.slice(0, k).map((s) => s[1]);
  }

  const SPLIT = /\s*(?:[,;]|->|=>|\bthen\b|\bafter that\b|\bafterwards\b|\band also\b|\band\b(?=\s+(?:open|create|send|post|notify|page|file|raise|tag|delete|close|resolve|snapshot|stop|assign|comment|message|alert|email|escalate|update|add|remove)\b))\s*/i;
  const ACTION = /^\W*(?:and\s+)?(?:please\s+)?(open|create|send|post|notify|page|file|raise|tag|delete|close|resolve|snapshot|stop|assign|comment|message|alert|email|escalate|update|add|remove|transition|invite|ask|approve|if)\b/i;
  const clauses = (t) => t.split(SPLIT).map((c) => (c || "").trim()).filter(Boolean);

  function tag(text, kind) { return el("span", `tag ${kind}`, text); }
  function effectTag(p) { return tag(p.e, p.e); }

  function tableCard(t) {
    const card = el("div", "res"), btn = el("button"); btn.setAttribute("aria-expanded", "false");
    btn.append(el("div", "nm", t.n), el("div", "ds", t.d));
    const meta = el("div", "meta", ""); meta.append(tag(t.p, ""), el("span", "ds", `${t.c.length} columns`));
    if (t.r) meta.append(tag("needs: " + t.r, "change"));
    btn.append(meta);
    const det = el("div", "detail");
    btn.addEventListener("click", () => {
      const open = card.classList.toggle("open"); btn.setAttribute("aria-expanded", String(open));
      if (open && !det.childElementCount) {
        const tbl = el("table", "t"), head = el("tr");
        for (const h of ["column", "type", "filter"]) head.append(el("th", "", h));
        tbl.append(head);
        for (const [n, ty] of t.c) {
          const tr = el("tr"); tr.append(el("td", "", n), el("td", "", ty), el("td", "", (t.f || []).includes(n) ? "fast" : ""));
          tbl.append(tr);
        }
        det.append(tbl, el("p", "ds", ""), el("code", "", `opslens describe table ${t.n}`));
      }
    });
    card.append(btn, det);
    return card;
  }

  function pipeCard(p) {
    const card = el("div", "res"), btn = el("button"); btn.setAttribute("aria-expanded", "false");
    btn.append(el("div", "nm", `${p.m}.${p.s}`), el("div", "ds", p.d || p.t));
    const meta = el("div", "meta"); meta.append(effectTag(p));
    const need = p.p.filter((x) => x.r && !x.t.startsWith("connection.") && x.t !== "notifier");
    if (need.length) meta.append(el("span", "ds", "needs " + need.map((x) => x.n).join(", ")));
    btn.append(meta);
    const det = el("div", "detail");
    btn.addEventListener("click", () => {
      const open = card.classList.toggle("open"); btn.setAttribute("aria-expanded", String(open));
      if (open && !det.childElementCount) {
        const tbl = el("table", "t"), head = el("tr");
        for (const h of ["param", "type", "required", "description"]) head.append(el("th", "", h));
        tbl.append(head);
        for (const x of p.p) {
          const tr = el("tr"); tr.append(el("td", "", x.n), el("td", "", x.t.length > 40 ? x.t.slice(0, 39) + "…" : x.t), el("td", "", x.r ? "yes" : ""), el("td", "", x.d || ""));
          tbl.append(tr);
        }
        const use = el("pre", "code", `step "pipeline" "${p.s}" {\n  pipeline = ${p.m}.pipeline.${p.s}\n  args = {\n${need.map((x) => `    ${x.n} = <${x.t}>`).join("\n")}\n  }\n}`);
        det.append(tbl, use, el("code", "", `opslens describe pipeline ${p.m}.${p.s}`));
      }
    });
    card.append(btn, det);
    return card;
  }

  function column(title, items, make, empty) {
    const c = el("div", "col"); c.append(el("h4", "", title));
    if (!items.length) c.append(el("div", "empty", empty)); else items.forEach((i) => c.append(make(i)));
    return c;
  }

  function render() {
    const text = input.value.trim();
    out.replaceChildren();
    if (!text) { out.append(el("div", "empty", "Describe what you want to find or do.")); return; }
    if (mode === "tables") { out.append(column("Tables", findTables(text, 12), tableCard, "No matching tables.")); return; }
    if (mode === "pipelines") { out.append(column("Pipelines", findPipes(text, 12), pipeCard, "No matching pipelines.")); return; }
    const cl = clauses(text);
    const data = cl.filter((c) => !ACTION.test(c)), acts = cl.filter((c) => ACTION.test(c));
    const grid = el("div", "cols2");
    grid.append(column("Data · Steampipe tables", findTables((data.length ? data : cl.slice(0, 1)).join(" "), 5), tableCard, "No matching tables."));
    const right = el("div", "col"); right.append(el("h4", "", "Actions · Flowpipe pipelines"));
    for (const c of acts.length ? acts : [text]) {
      right.append(el("div", "ds", `for: ${c}`));
      const hits = findPipes(c, 3);
      if (!hits.length) right.append(el("div", "empty", "No matching pipelines.")); else hits.forEach((p) => right.append(pipeCard(p)));
    }
    grid.append(right); out.append(grid);
  }

  let timer;
  input.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(render, 120); });
  for (const b of document.querySelectorAll("#modes .chip")) b.addEventListener("click", () => {
    mode = b.dataset.mode; document.querySelectorAll("#modes .chip").forEach((x) => x.setAttribute("aria-pressed", String(x === b))); render();
  });
  for (const a of document.querySelectorAll("#examples a")) a.addEventListener("click", () => { input.value = a.dataset.ex; input.focus(); render(); });
  load().then(() => { const p = new URLSearchParams(location.search).get("q"); if (p) { input.value = p; } render(); })
        .catch(() => { status.textContent = "Could not load the catalogs. Reload to try again."; });
})();
