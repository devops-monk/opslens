/* opslens app. A visual flow builder over the same engine as the CLI.
   Safety: every dynamic string reaches the page through DOM text nodes / setAttribute, never innerHTML. */
(() => {
  "use strict";

  // ---------------------------------------------------------------- tiny DOM kit
  const $ = (s, r = document) => r.querySelector(s);
  function add(e, kids) { for (const k of kids.flat(Infinity)) { if (k == null || k === false) continue; e.append(k instanceof Node ? k : document.createTextNode(String(k))); } return e; }
  function h(tag, props, ...kids) {
    const e = document.createElement(tag); let value;
    for (const [k, v] of Object.entries(props || {})) {
      if (v == null || v === false) continue;
      if (k === "class") e.className = v;
      else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
      else if (k === "value") value = v;
      else if (k === "style") e.style.cssText = v; // CSSOM, so it also works under a strict CSP
      else if (k === "checked" || k === "disabled" || k === "hidden" || k === "selected") e[k] = !!v;
      else e.setAttribute(k, v === true ? "" : String(v));
    }
    add(e, kids); if (value !== undefined) e.value = value; return e;
  }
  const NS = "http://www.w3.org/2000/svg";
  const ICON = {
    clock: ["M3 12a9 9 0 1 0 18 0a9 9 0 1 0 -18 0", "M12 7v5l3 2"], play: ["M8 5v14l11-7z"], bolt: ["M13 2L4 14h7l-1 8 9-12h-7z"],
    db: ["M4 6c0-1.7 3.6-3 8-3s8 1.3 8 3-3.6 3-8 3-8-1.3-8-3z", "M4 6v6c0 1.7 3.6 3 8 3s8-1.3 8-3V6", "M4 12v6c0 1.7 3.6 3 8 3s8-1.3 8-3v-6"],
    shield: ["M12 3l8 3v6c0 4.5-3.2 8-8 9-4.8-1-8-4.5-8-9V6z", "M9 12l2 2 4-4"], plus: ["M12 5v14M5 12h14"],
    trash: ["M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"], check: ["M5 12l5 5 9-10"], alert: ["M12 4l9 16H3z", "M12 10v4M12 17.5v.5"],
    code: ["M8 8l-4 4 4 4M16 8l4 4-4 4M14 5l-4 14"], x: ["M6 6l12 12M18 6L6 18"], back: ["M15 5l-7 7 7 7"],
    sliders: ["M4 7h10M18 7h2M4 17h2M10 17h10M14 5v4M6 15v4"], search: ["M3 11a8 8 0 1 0 16 0a8 8 0 1 0 -16 0", "M16.5 16.5L21 21"],
    sparkle: ["M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z", "M19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z"],
    hand: ["M7 11V6a1.5 1.5 0 0 1 3 0v4M10 10V4.5a1.5 1.5 0 0 1 3 0V10M13 10V5.5a1.5 1.5 0 0 1 3 0V11M16 11V8.5a1.5 1.5 0 0 1 3 0V14c0 4-2.5 7-6.5 7S7 18.5 5.5 15.5L4 12.5a1.5 1.5 0 0 1 2.6-1.5L7 12"],
  };
  function ic(name) { const s = document.createElementNS(NS, "svg"); s.setAttribute("viewBox", "0 0 24 24"); s.setAttribute("class", "i"); s.setAttribute("aria-hidden", "true"); for (const d of ICON[name] || []) { const p = document.createElementNS(NS, "path"); p.setAttribute("d", d); s.append(p); } return s; }
  const APP_LABEL = { aws: "aws", gitlab: "GL", jira: "Ji", opsgenie: "Og", teams: "Tm", slack: "Sl", steampipe: "SQL" };
  const APP_NAME = { aws: "AWS", gitlab: "GitLab", jira: "Jira", opsgenie: "Opsgenie", teams: "Teams", slack: "Slack" };
  function appBadge(key, size) {
    const k = APP_LABEL[key] ? key : "generic";
    return h("span", { class: `app ${k}`, style: `--s:${size || 34}px`, title: APP_NAME[key] || key, "aria-label": APP_NAME[key] || key }, APP_LABEL[key] || (key || "?").slice(0, 2));
  }
  function kindBadge(kind, name) { return h("span", { class: `app kind-${kind}`, style: "--s:38px", "aria-hidden": "true" }, ic(name)); }
  const tagEl = (txt, kind) => h("span", { class: `tag ${kind || ""}` }, txt);
  const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };
  function toast(msg, ms = 4200) { const t = h("div", { class: "toast", role: "status" }, msg); document.body.append(t); setTimeout(() => t.remove(), ms); }

  // ---------------------------------------------------------------- api
  let meta = null;
  async function api(path, body, method) {
    const opt = { method: method || (body === undefined ? "GET" : "POST"), headers: {} };
    if (body !== undefined) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
    if (opt.method !== "GET") opt.headers["X-Opslens-Token"] = meta ? meta.token : "";
    const r = await fetch(path.replace(/^\//, ""), opt); // relative, so the app also works under a path prefix (/app/)
    let data = null; try { data = await r.json(); } catch (_) { /* empty */ }
    if (!r.ok) throw new Error(typeof (data && data.detail) === "string" ? data.detail : `${r.status} ${r.statusText}`);
    return data;
  }

  // ---------------------------------------------------------------- state
  const blank = () => ({ name: "new_automation", title: "", description: "", request: "", variables: {}, trigger: { kind: "manual", schedule: "daily" },
    detect: { sql: "", max_items: 50 }, notify: true, approval: { prompt: "Approve the gated actions for these items?" }, actions: [], auto_apply: false });
  const S = { view: "home", spec: blank(), sel: null, val: null, results: null, packs: [], cat: "all", nameLocked: false, pickFor: null, lastField: null, seq: 0, ai: "" };
  const pipeData = new Map();
  async function pipeAsync(name) {
    if (pipeData.has(name)) return pipeData.get(name);
    let d = null; try { d = await api(`/api/pipeline/${encodeURIComponent(name)}`); } catch (_) { d = null; }
    pipeData.set(name, d); return d;
  }
  const pipe = (name) => pipeData.get(name) || null;
  const params = (p) => (p ? p.params.filter((x) => !x.type.startsWith("connection.") && x.type !== "notifier") : []);
  const effectOf = (name) => (pipe(name) ? pipe(name).effect : "notify");
  const modOf = (name) => String(name).split(".")[0];
  const slug = (t) => { let s = t.toLowerCase().replace(/[^a-z0-9]+/g, "_").replace(/^_+|_+$/g, ""); if (!/^[a-z]/.test(s)) s = `a_${s}`; s = s.slice(0, 63); return s.length < 2 ? "automation" : s; };
  const tablesOf = (sql) => [...new Set([...String(sql).matchAll(/\b(?:from|join)\s+([a-z0-9_]+)/gi)].map((m) => m[1].toLowerCase()))];
  const TABLE_APPS = [["aws_", "aws"], ["gitlab_", "gitlab"], ["jira_", "jira"], ["opsgenie_", "opsgenie"], ["microsoft365_", "teams"], ["teams_", "teams"]];
  const appOfTable = (t) => { const m = TABLE_APPS.find(([p]) => t.startsWith(p)); return m ? m[1] : "steampipe"; };
  const SCHED = { hourly: "Every hour", daily: "Every day", weekly: "Every week", "15m": "Every 15 minutes", "30m": "Every 30 minutes", "6h": "Every 6 hours", "12h": "Every 12 hours" };
  const triggerTitle = (t) => (t.kind === "manual" ? "Run on demand" : SCHED[t.schedule] || `On schedule: ${t.schedule}`);
  const cols = () => (S.val && S.val.columns) || [];
  const gatedSteps = () => S.spec.actions.map((a, i) => [a, i]).filter(([a]) => a.gated);
  const incomplete = () => {
    const s = S.spec, q = s.detect.sql.trim().length < 7;
    if (q && !s.actions.length) return "Start at step 2: say what to look for. Then add an action.";
    if (q) return "Step 2 needs a query: say what to look for.";
    if (!s.actions.length) return "Add at least one action.";
    return null;
  };

  // ---------------------------------------------------------------- validation (server is the single source of truth)
  const scheduleValidate = debounce(() => revalidate(), 350);
  async function revalidate() {
    const my = ++S.seq, miss = incomplete();
    if (miss) {
      let columns = [], extra = [];
      if (S.spec.detect.sql.trim().length >= 7) { // the query is written but the spec is not complete: still help with its columns
        try { const r = await api("/api/columns", { sql: S.spec.detect.sql }); if (my !== S.seq) return; columns = r.columns; if (r.error) extra = [{ level: "error", code: "sql", message: r.error, where: "detect.sql" }]; } catch (_) { /* leave empty */ }
      }
      S.val = { ok: false, pending: !extra.length, issues: [...extra, { level: "error", code: "incomplete", message: miss, where: "" }], columns, explain: [], hash: null, gated: [] };
    } else {
      try { const v = await api("/api/validate", { spec: S.spec }); if (my !== S.seq) return; S.val = v; }
      catch (e) { if (my !== S.seq) return; S.val = { ok: false, issues: [{ level: "error", code: "api", message: e.message, where: "" }], columns: cols(), explain: [], hash: null, gated: [] }; }
    }
    if (S.view === "builder") { renderStatus(); renderIssues(); renderCanvas(); refreshDynamic(); if (S.sel === null) renderPanel(); }
  }
  function touch() { renderCanvas(); scheduleValidate(); if (S.view === "builder") renderStatus(true); }
  function stepOfIssue(i) {
    const w = i.where || "", m = w.match(/^actions\[(\d+)\]/);
    if (m) return `a${Number(m[1]) - 1}`; if (w.startsWith("detect")) return "find"; if (w.startsWith("trigger")) return "trigger"; if (w.startsWith("variables")) return "settings";
    return null;
  }

  // ---------------------------------------------------------------- navigation
  const VIEWS = ["home", "builder", "explore", "mine"];
  function show(view, push) {
    S.view = view;
    for (const v of VIEWS) $(`#v-${v}`).hidden = v !== view;
    for (const t of document.querySelectorAll(".tab")) t.setAttribute("aria-selected", String(t.dataset.view === view));
    document.title = `${{ home: "Templates", builder: "Builder", explore: "Explore", mine: "My automations" }[view]} · opslens`;
    if (push !== false) { try { history.replaceState(null, "", view === "home" ? location.pathname : `?view=${view}`); } catch (_) { /* file:// etc. */ } }
    if (view === "builder") renderBuilder();
    if (view === "mine") loadMods();
    window.scrollTo(0, 0);
  }
  for (const t of document.querySelectorAll(".tab")) t.addEventListener("click", () => show(t.dataset.view));

  // ---------------------------------------------------------------- home: ask + templates
  const EXAMPLES = ["Unattached EBS volumes: open a Jira ticket, then delete after I approve", "EC2 instances missing an Owner tag", "Page me when GuardDuty finds something serious", "Who deployed what when this alert fired?"];
  const CATS = { all: "All", "finops-cleanup": "Cost", governance: "Governance", security: "Security", incident: "Incident response" };
  function renderHome() {
    const ai = meta.ai && meta.mode !== "demo";
    $("#askgo").replaceChildren(ic(ai ? "sparkle" : "search"), ai ? "Draft with AI" : "Find tables & actions");
    $("#askhint").textContent = ai ? `Drafted by ${meta.provider}. You read it before anything runs.` : "Searches the built-in catalog of tables and actions. No AI needed.";
    const ex = $("#examples"); ex.replaceChildren(...EXAMPLES.map((t) => h("button", { class: "chip", type: "button", onclick: () => { $("#ask").value = t; $("#ask").focus(); } }, t)));
    const cats = $("#cats"); const present = ["all", ...new Set(S.packs.map((p) => p.category))];
    cats.replaceChildren(...present.map((c) => h("button", { class: "chip", role: "tab", "aria-selected": String(S.cat === c), onclick: () => { S.cat = c; renderHome(); } }, CATS[c] || c)));
    const grid = $("#templates"); grid.replaceChildren();
    grid.append(h("button", { class: "tpl blank", onclick: () => startBlank() }, h("span", { class: "plus" }, ic("plus")), h("h3", {}, "Start from scratch"), h("span", { class: "muted" }, "Choose a trigger, what to find, and what to do.")));
    for (const p of S.packs.filter((x) => S.cat === "all" || x.category === S.cat)) grid.append(templateCard(p));
  }
  function templateCard(p) {
    const gated = p.steps.some((s) => s.gated), nChange = p.steps.filter((s) => s.effect === "change").length;
    const sched = p.schedule ? (SCHED[p.schedule] || p.schedule) : "On demand";
    return h("button", { class: "tpl", onclick: () => loadPack(p.pack) },
      h("span", { class: "cat" }, CATS[p.category] || p.category),
      h("div", { class: "apps" }, ...p.apps.map((a) => appBadge(a, 32))),
      h("h3", {}, p.title), h("p", {}, p.description),
      h("div", { class: "flowline" }, tagEl(sched, ""), tagEl(`${p.steps.length} action${p.steps.length === 1 ? "" : "s"}`, ""), gated ? tagEl("Asks before changing", "change") : tagEl(nChange ? "Changes things" : "Read & notify only", nChange ? "change" : "read")),
      h("div", { class: "foot" }, h("span", { class: "btn primary sm" }, "Use this template"), h("span", { class: "muted" }, p.pack.split("/")[0])));
  }
  $("#ask").addEventListener("keydown", (e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); $("#askform").requestSubmit(); } });
  $("#askform").addEventListener("submit", async (e) => {
    e.preventDefault(); const text = $("#ask").value.trim(); if (!text) { $("#ask").focus(); return; }
    if (!(meta.ai && meta.mode !== "demo")) { $("#q").value = text; show("explore"); runSearch(); return; }
    const btn = $("#askgo"); btn.disabled = true; $("#askhint").textContent = `Asking ${meta.provider}…`;
    try {
      const r = await api("/api/generate", { requirement: text });
      await loadSpec(r.spec, { ai: `Drafted by ${r.model} in ${r.attempts} attempt${r.attempts > 1 ? "s" : ""}. Read every step before you trust it.`, lock: false });
    } catch (err) { $("#askhint").textContent = err.message; toast(err.message, 7000); } finally { btn.disabled = false; }
  });

  // ---------------------------------------------------------------- load / start
  async function loadSpec(spec, opts = {}) {
    S.spec = { ...blank(), ...spec, trigger: { ...blank().trigger, ...(spec.trigger || {}) }, detect: { ...blank().detect, ...spec.detect }, approval: { ...blank().approval, ...(spec.approval || {}) } };
    S.nameLocked = opts.lock !== false; S.results = null; S.sel = null; S.pickFor = null; S.ai = opts.ai || ""; S.val = null;
    await Promise.all(S.spec.actions.map((a) => pipeAsync(a.pipeline)));
    show("builder"); await revalidate();
  }
  async function loadPack(name) { try { const r = await api(`/api/packs/${name}`); await loadSpec(r.spec); } catch (e) { toast(e.message, 7000); } }
  function startBlank() { S.spec = blank(); S.nameLocked = false; S.results = null; S.sel = "find"; S.pickFor = null; S.ai = ""; S.val = null; show("builder"); revalidate(); }

  // ---------------------------------------------------------------- builder: header
  function renderBuilder() {
    $("#b-back").replaceChildren(ic("back")); $("#b-yaml").replaceChildren(ic("code"), "YAML"); $("#b-settings").replaceChildren(ic("sliders"), "Settings");
    $("#b-test").replaceChildren(ic("play"), "Test");
    $("#b-title").value = S.spec.title; $("#b-save").hidden = meta.mode === "demo"; $("#b-test-live").hidden = meta.mode === "demo";
    renderCanvas(); renderPanel(); renderStatus(); renderIssues(); renderResults();
  }
  $("#b-back").addEventListener("click", () => show("home"));
  $("#b-title").addEventListener("input", (e) => { S.spec.title = e.target.value; if (!S.nameLocked) S.spec.name = slug(e.target.value || "new automation"); touch(); });
  $("#b-settings").addEventListener("click", () => select("settings"));
  function renderStatus(pending) {
    const b = $("#b-status"), v = S.val; b.replaceChildren(); b.className = "status";
    if (pending || !v) { b.classList.add("pend"); b.append("Checking…"); return; }
    if (v.ok) { b.classList.add("good"); b.append(ic("check"), v.issues.length ? `Valid · ${v.issues.length} note${v.issues.length > 1 ? "s" : ""}` : "Valid"); b.title = `spec hash ${v.hash}`; }
    else if (v.pending) { b.classList.add("pend"); b.append("Not finished"); b.title = ""; }
    else { const n = v.issues.filter((i) => i.level === "error").length || v.issues.length; b.classList.add("badn"); b.append(ic("alert"), `${n} issue${n > 1 ? "s" : ""} to fix`); b.title = ""; }
  }
  $("#b-status").addEventListener("click", () => { const p = $("#b-issues"); p.hidden = !p.hidden || !(S.val && S.val.issues.length); $("#b-status").setAttribute("aria-expanded", String(!p.hidden)); });
  function renderIssues() {
    const p = $("#b-issues"), v = S.val; p.replaceChildren();
    if (!v || !v.issues.length) { p.hidden = true; return; }
    for (const i of v.issues) {
      p.append(h("button", { class: "issue", onclick: () => { const k = stepOfIssue(i); if (k) select(k); } }, h("span", { class: `lv ${i.level}` }, i.level), h("span", { class: "grow" }, i.message), i.where ? h("span", { class: "wh" }, i.where) : null));
    }
  }

  // ---------------------------------------------------------------- builder: canvas
  function select(key) { S.sel = key; S.pickFor = null; renderCanvas(); renderPanel(); $("#panel").classList.remove("closed"); }
  function step(key, { icon, kind, title, sub, side, cls }) {
    const bad = S.val && S.val.issues.some((i) => stepOfIssue(i) === key);
    return h("button", { class: `step ${cls || ""} ${bad ? "has-issue" : ""}`, "aria-pressed": String(S.sel === key), onclick: () => select(key) },
      icon, h("div", { class: "txt" }, h("div", { class: "kind" }, kind), h("div", { class: "ttl" }, title), sub ? h("div", { class: "sub" }, sub) : null), side ? h("div", { class: "side" }, side) : null);
  }
  const link = () => h("div", { class: "link", "aria-hidden": "true" });
  function renderCanvas() {
    const f = $("#flow"); if (!f) return; f.replaceChildren();
    const s = S.spec, tbs = tablesOf(s.detect.sql), cs = cols();
    f.append(step("trigger", { icon: kindBadge("trigger", s.trigger.kind === "manual" ? "hand" : "clock"), kind: "1 · Trigger", title: triggerTitle(s.trigger), sub: s.trigger.kind === "schedule" ? "Switched on when you deploy" : "Start it from the app or the command line" }), link());
    const findApps = [...new Set(tbs.map(appOfTable))];
    f.append(step("find", { icon: findApps.length === 1 ? appBadge(findApps[0], 38) : kindBadge("find", "db"), kind: "2 · Find", title: tbs.length ? `Look at ${tbs.join(", ")}` : "Choose what to look at",
      sub: s.detect.sql.trim().length < 7 ? "Read-only query. Nothing is changed." : (cs.length ? `${cs.slice(0, 4).join(", ")}${cs.length > 4 ? ` +${cs.length - 4} more` : ""} · up to ${s.detect.max_items} rows` : `up to ${s.detect.max_items} rows`),
      side: S.results ? tagEl(`${S.results.items} found in test`, "read") : null }), link());
    const idx = s.actions.map((_, i) => i), now = idx.filter((i) => !s.actions[i].gated), later = idx.filter((i) => s.actions[i].gated);
    const actionCard = (i, n) => {
      const a = s.actions[i], p = pipe(a.pipeline), eff = p ? p.effect : "notify";
      return step(`a${i}`, { icon: appBadge(modOf(a.pipeline), 38), kind: `${n} · ${a.gated ? "Action after approval" : "Action"}`, title: a.title || (p ? p.title : a.pipeline), sub: a.pipeline,
        side: [tagEl(eff === "change" ? "Changes things" : eff === "notify" ? "Creates / notifies" : "Read-only", eff), a.gated ? tagEl("You approve", "change") : null] });
    };
    let n = 3;
    for (const i of now) { f.append(actionCard(i, n++), link()); }
    if (later.length) {
      f.append(step("approval", { cls: "approval", icon: kindBadge("approval", "shield"), kind: `${n++} · Approval`, title: "You review before the next steps", sub: `${later.length} step${later.length > 1 ? "s" : ""} wait for your yes` }), link());
      for (const i of later) { f.append(actionCard(i, n++), link()); }
    }
    f.append(h("button", { class: "add", onclick: () => openPicker(null) }, ic("plus"), s.actions.length ? "Add another action" : "Add an action"));
  }

  // ---------------------------------------------------------------- builder: panel
  function renderPanel() {
    const p = $("#panel"); if (!p) return; p.replaceChildren();
    p.classList.toggle("closed", S.sel === null);
    const k = S.sel;
    if (k === "trigger") return panelTrigger(p);
    if (k === "find") return panelFind(p);
    if (k === "approval") return panelApproval(p);
    if (k === "settings") return panelSettings(p);
    if (k === "picker") return panelPicker(p);
    if (k && k.startsWith("a")) return panelAction(p, Number(k.slice(1)));
    panelOverview(p);
  }
  function head(icon, title, sub) {
    return h("div", { class: "ph" }, icon, h("div", { class: "grow" }, h("h3", {}, title), sub ? h("p", { class: "sub" }, sub) : null), h("button", { class: "icon-btn", "aria-label": "Close panel", onclick: () => { S.sel = null; renderCanvas(); renderPanel(); } }, ic("x")));
  }
  function panelOverview(p) {
    const v = S.val;
    p.append(h("h3", {}, "How this runs"), h("p", { class: "sub" }, "Click any step to edit it."));
    if (S.ai) p.append(h("div", { class: "sw on locked" }, h("div", {}, h("b", {}, "AI-drafted"), h("span", {}, S.ai))));
    if (v && v.explain && v.explain.length) p.append(h("ul", { class: "explain" }, ...v.explain.map((x) => h("li", {}, x))));
    else p.append(h("div", { class: "empty sp" }, (v && v.issues[0] && v.issues[0].message) || "Pick a template or add steps; this panel explains what the automation will do in plain English."));
    if (v && v.hash) p.append(h("h4", {}, "Spec hash"), h("p", { class: "mono" }, v.hash), h("p", { class: "muted" }, "A deploy is tied to this exact hash, so what you reviewed is what runs."));
  }
  function panelTrigger(p) {
    const t = S.spec.trigger, known = Object.keys(SCHED), custom = t.kind === "schedule" && !known.includes(t.schedule);
    p.append(head(kindBadge("trigger", "clock"), "Trigger", "What starts this automation."));
    const seg = (k, title, desc) => h("button", { "aria-pressed": String(t.kind === k), onclick: () => { t.kind = k; touch(); renderPanel(); } }, h("b", {}, title), h("span", {}, desc));
    p.append(h("div", { class: "seg" }, seg("manual", "On demand", "You start it when you want"), seg("schedule", "On a schedule", "It runs by itself")));
    if (t.kind === "schedule") {
      const sel = h("select", { "aria-label": "How often", onchange: (e) => { if (e.target.value === "custom") { t.schedule = "0 * * * *"; renderPanel(); } else t.schedule = e.target.value; touch(); } },
        ...known.map((k) => h("option", { value: k, selected: !custom && t.schedule === k }, SCHED[k])), h("option", { value: "custom", selected: custom }, "Custom (cron)…"));
      p.append(h("label", { class: "f" }, "How often", sel));
      if (custom) p.append(h("label", { class: "f" }, "Cron expression", h("small", {}, "Five fields: minute hour day month weekday. Nothing tighter than every 5 minutes."), h("input", { type: "text", class: "mono", value: t.schedule, oninput: (e) => { t.schedule = e.target.value; touch(); } })));
      p.append(h("p", { class: "muted sp" }, "Schedules ship switched off. You turn them on when you deploy."));
    }
  }
  function panelFind(p) {
    const s = S.spec;
    p.append(head(kindBadge("find", "db"), "Find", "A read-only query over your cloud and tools. It can never change anything."));
    p.append(h("label", { class: "f" }, "What should it look for?", h("small", {}, "SQL over the Steampipe tables. List the columns you need (no SELECT *)."),
      h("textarea", { class: "sql", spellcheck: "false", placeholder: "select\n  volume_id,\n  region\nfrom aws_ebs_volume\nwhere state = 'available'", oninput: (e) => { s.detect.sql = e.target.value; touch(); } }, s.detect.sql)));
    p.append(h("h4", {}, "Columns your actions can use"), h("div", { class: "cols", id: "cols-row" }));
    p.append(h("label", { class: "f" }, "Most rows to act on per run", h("small", {}, "A hard safety cap, 1 to 500."),
      h("input", { type: "number", min: "1", max: "500", value: s.detect.max_items, oninput: (e) => { s.detect.max_items = Math.max(1, Math.min(500, Number(e.target.value) || 50)); touch(); } })));
    p.append(h("h4", {}, "Not sure which table?"));
    const out = h("div", { id: "tbl-hits" });
    const box = h("input", { type: "search", placeholder: "Search tables: ebs volume, gitlab pipeline, jira issue…", "aria-label": "Search tables", oninput: debounce(async (e) => {
      const q = e.target.value.trim(); out.replaceChildren(); if (!q) return;
      try {
        const r = await api(`/api/search?q=${encodeURIComponent(q)}`);
        if (!r.tables.length) out.append(h("p", { class: "muted" }, "No matching tables."));
        for (const t of r.tables) out.append(h("button", { class: "pick", type: "button", onclick: () => useTable(t.table) }, appBadge(appOfTable(t.table), 30), h("div", {}, h("b", {}, t.table), h("span", { class: "d" }, t.description || ""))));
      } catch (err) { out.append(h("p", { class: "bad" }, err.message)); }
    }, 220) });
    p.append(box, out); refreshDynamic();
  }
  async function useTable(name) {
    try {
      const d = await api(`/api/table/${encodeURIComponent(name)}`), c = (d.columns || []).slice(0, 6).map((x) => x.name);
      if (S.spec.detect.sql.trim() && !confirm("Replace the current query with a starter query for this table?")) return;
      S.spec.detect.sql = `select\n  ${c.join(",\n  ")}\nfrom ${name}`; S.val = S.val ? { ...S.val, columns: c } : S.val; touch(); renderPanel();
    } catch (e) { toast(e.message); }
  }
  function panelApproval(p) {
    p.append(head(kindBadge("approval", "shield"), "Approval", "A person says yes before anything that changes things."));
    p.append(h("p", {}, "Steps marked “You approve” wait here. Nothing after this point runs until you approve it. Skipping or declining stops the run."),
      h("label", { class: "f" }, "What the approval asks", h("textarea", { rows: 3, oninput: (e) => { S.spec.approval.prompt = e.target.value; touch(); } }, S.spec.approval.prompt)));
  }
  function panelSettings(p) {
    const s = S.spec;
    p.append(head(kindBadge("find", "sliders"), "Settings", "Name, description and the values you can change without editing the steps."));
    p.append(h("label", { class: "f" }, "Name", h("input", { type: "text", maxlength: "80", value: s.title, oninput: (e) => { s.title = e.target.value; $("#b-title").value = e.target.value; if (!S.nameLocked) { s.name = slug(e.target.value); $("#set-id").textContent = s.name; } touch(); } })),
      h("p", { class: "muted" }, "ID: ", h("span", { class: "mono", id: "set-id" }, s.name)),
      h("label", { class: "f" }, "Description", h("textarea", { rows: 3, oninput: (e) => { s.description = e.target.value; touch(); } }, s.description)));
    p.append(h("h4", {}, "Variables"), h("p", { class: "muted" }, "Named values your steps can use as {var.name}, such as a Jira project. Change them without touching the steps."));
    const list = h("div"); p.append(list, h("button", { class: "btn ghost sm sp", type: "button", onclick: () => { let n = 1; while (s.variables[`value_${n}`]) n++; s.variables[`value_${n}`] = { default: "", description: "" }; renderVars(list); touch(); } }, ic("plus"), "Add a variable")); renderVars(list);
    p.append(h("label", { class: "sw" + (s.notify ? " on" : ""), }, h("input", { type: "checkbox", checked: s.notify, onchange: (e) => { s.notify = e.target.checked; e.target.parentElement.classList.toggle("on", s.notify); touch(); } }), h("div", {}, h("b", {}, "Post a summary when something is found"), h("span", {}, "One line through the notifier you configure when you deploy."))));
  }
  function renderVars(list) {
    list.replaceChildren(); const s = S.spec;
    for (const [k, v] of Object.entries(s.variables)) {
      list.append(h("div", { class: "varrow" },
        h("input", { type: "text", class: "mono", value: k, "aria-label": "Variable name", onchange: (e) => { const nk = e.target.value.trim().replace(/[^A-Za-z0-9_]/g, "_"); if (!nk || nk === k || s.variables[nk]) { e.target.value = k; return; } const o = {}; for (const [a, b] of Object.entries(s.variables)) o[a === k ? nk : a] = b; s.variables = o; renderVars(list); touch(); } }),
        h("input", { type: "text", value: String(v.default), "aria-label": "Default value", placeholder: "default", oninput: (e) => { v.default = e.target.value; touch(); } }),
        h("button", { class: "icon-btn", type: "button", "aria-label": `Remove ${k}`, onclick: () => { delete s.variables[k]; renderVars(list); touch(); } }, ic("trash")),
        h("input", { type: "text", class: "desc", value: v.description || "", placeholder: "what is this for?", "aria-label": "Description", oninput: (e) => { v.description = e.target.value; touch(); } })));
    }
    if (!Object.keys(s.variables).length) list.append(h("p", { class: "muted" }, "None yet."));
  }

  // ---- action editor
  function panelAction(p, i) {
    const a = S.spec.actions[i]; if (!a) { S.sel = null; return renderPanel(); }
    const d = pipe(a.pipeline), eff = d ? d.effect : "notify", ps = params(d);
    p.append(head(appBadge(modOf(a.pipeline), 40), a.title || (d ? d.title : a.pipeline), a.pipeline));
    p.append(h("div", { class: "row", style: "display:flex;gap:8px;align-items:center;flex-wrap:wrap" }, tagEl(eff === "change" ? "Changes things" : eff === "notify" ? "Creates / notifies" : "Read-only", eff), h("button", { class: "btn ghost sm", type: "button", onclick: () => openPicker(i) }, "Change action")));
    if (d && d.description) p.append(h("p", { class: "muted sp" }, d.description.split(/(?<=[.!?])\s/)[0]));
    if (!d) p.append(h("p", { class: "bad sp" }, `${a.pipeline} is not in the catalog.`));
    p.append(h("label", { class: "f" }, "Step name (optional)", h("small", {}, "Shown in the flow and in the approval."), h("input", { type: "text", maxlength: "80", value: a.title || "", placeholder: d ? d.title : "", oninput: (e) => { a.title = e.target.value; touch(); } })));
    const req = ps.filter((x) => x.required), opt = ps.filter((x) => !x.required);
    p.append(h("h4", {}, "Fill in the details"), h("div", { class: "cols", id: "ph-row" }));
    for (const x of req) p.append(field(a, x));
    if (!req.length) p.append(h("p", { class: "muted" }, "This action needs nothing else."));
    if (opt.length) p.append(h("details", { class: "more" }, h("summary", {}, `More options (${opt.length})`), ...opt.map((x) => field(a, x))));
    const locked = eff === "change";
    p.append(h("label", { class: "sw" + (a.gated ? " on" : "") + (locked ? " locked" : "") }, h("input", { type: "checkbox", checked: a.gated || locked, disabled: locked, onchange: (e) => { a.gated = e.target.checked; e.target.parentElement.classList.toggle("on", a.gated); touch(); } }),
      h("div", {}, h("b", {}, locked ? "Needs your approval (required)" : "Ask me before this runs"), h("span", {}, locked ? "This changes things, so it always waits for a yes." : "Off: runs automatically. On: it waits for your approval."))));
    p.append(h("button", { class: "btn ghost sm sp", type: "button", style: "color:var(--red)", onclick: () => { S.spec.actions.splice(i, 1); S.sel = null; touch(); renderPanel(); } }, ic("trash"), "Remove this step"));
    refreshDynamic();
  }
  function field(a, x) {
    const cur = a.args[x.name], set = (v) => { if (v === "" || v == null) delete a.args[x.name]; else a.args[x.name] = v; touch(); };
    let ctl;
    if (x.enum && x.enum.length) ctl = h("select", { onchange: (e) => set(e.target.value), value: cur == null ? "" : String(cur) }, h("option", { value: "" }, "Choose…"), ...x.enum.map((o) => h("option", { value: String(o) }, String(o))));
    else if (x.type === "bool") ctl = h("select", { onchange: (e) => set(e.target.value), value: cur == null ? "" : String(cur) }, h("option", { value: "" }, "Default"), h("option", { value: "true" }, "Yes"), h("option", { value: "false" }, "No"));
    else ctl = h("input", { type: "text", class: "arg", value: cur == null ? "" : String(cur), placeholder: /map|list/.test(x.type) ? (x.type.startsWith("map") ? "key=value,key2=value2" : "one,two") : x.type, oninput: (e) => set(e.target.value), onfocus: (e) => { S.lastField = e.target; } });
    return h("label", { class: "f" }, x.name, x.required ? h("span", { class: "req" }, " *") : null, h("small", {}, x.description || x.type), ctl);
  }
  function refreshDynamic() {
    const c = $("#cols-row"); if (c) { c.replaceChildren(...(cols().length ? cols().map((n) => h("span", { class: "chip mono" }, n)) : [h("span", { class: "muted" }, "Write the query and they appear here.")])); }
    const r = $("#ph-row"); if (r) {
      const items = [...cols().map((n) => `{${n}}`), ...Object.keys(S.spec.variables).map((n) => `{var.${n}}`)];
      r.replaceChildren(...(items.length ? [h("span", { class: "muted" }, "Click to insert a value from the row:"), ...items.map((t) => h("button", { class: "chip mono", type: "button", onmousedown: (e) => e.preventDefault(), onclick: () => insertAtCaret(t) }, t))] : [h("span", { class: "muted" }, "Write the query first; its columns can then be inserted here.")]));
    }
  }
  function insertAtCaret(text) {
    const f = S.lastField; if (!f || !document.contains(f)) { toast("Click a field first, then pick a value."); return; }
    const s = f.selectionStart ?? f.value.length, e = f.selectionEnd ?? s; f.value = f.value.slice(0, s) + text + f.value.slice(e);
    f.setSelectionRange(s + text.length, s + text.length); f.dispatchEvent(new Event("input", { bubbles: true })); f.focus();
  }

  // ---- action picker
  function openPicker(forIdx) { S.sel = "picker"; S.pickFor = forIdx; renderCanvas(); renderPanel(); $("#panel").classList.remove("closed"); }
  function panelPicker(p) {
    p.append(head(kindBadge("find", "bolt"), S.pickFor == null ? "Add an action" : "Change the action", "What should happen for each thing it finds? Search every action across AWS, GitLab, Jira, Opsgenie and Teams."));
    const out = h("div"), other = h("input", { type: "checkbox" });
    const run = async (q) => {
      out.replaceChildren(h("p", { class: "muted" }, "Searching…"));
      try {
        const rows = await api(`/api/pipelines?q=${encodeURIComponent(q)}&other=${other.checked}`); out.replaceChildren();
        if (!rows.length) out.append(h("p", { class: "muted" }, "No matching actions. Try other words, like “jira ticket” or “tag ec2”."));
        for (const r of rows) out.append(h("button", { class: "pick", type: "button", onclick: () => choose(r) }, appBadge(r.mod, 32), h("div", {}, h("b", {}, r.pipeline), h("span", { class: "d" }, r.description || r.title), h("span", { class: "d" }, tagEl(r.effect === "change" ? "Changes things" : r.effect === "notify" ? "Creates / notifies" : "Read-only", r.effect)))));
      } catch (e) { out.replaceChildren(h("p", { class: "bad" }, e.message)); }
    };
    const box = h("input", { type: "search", placeholder: "e.g. open a jira ticket, post to teams, tag ec2 instances", "aria-label": "Search actions" });
    box.addEventListener("input", debounce(() => run(box.value), 220)); other.addEventListener("change", () => run(box.value));
    p.append(box, h("label", { class: "row sp", style: "display:flex;gap:8px;align-items:center;font-size:13px;color:var(--fg2)" }, other, "Include other services (Slack, ClickUp, OpenAI, …)"), out); run(""); setTimeout(() => box.focus(), 30);
  }
  async function choose(row) {
    const d = await pipeAsync(row.pipeline); if (!d) { toast("That action is not in the catalog."); return; }
    const mapped = {}; for (const x of params(d)) if (cols().includes(x.name)) mapped[x.name] = `{${x.name}}`;
    const change = d.effect === "change";
    if (S.pickFor == null) { S.spec.actions.push({ pipeline: row.pipeline, args: mapped, gated: change, title: "" }); S.sel = `a${S.spec.actions.length - 1}`; }
    else { const a = S.spec.actions[S.pickFor]; a.pipeline = row.pipeline; a.args = mapped; a.gated = change || a.gated; S.sel = `a${S.pickFor}`; }
    S.pickFor = null; renderCanvas(); renderPanel(); scheduleValidate();
  }
  async function addAction(name) { // used by Explore
    const d = await pipeAsync(name); if (!d) return; const mapped = {};
    S.spec.actions.push({ pipeline: name, args: mapped, gated: d.effect === "change", title: "" }); S.sel = `a${S.spec.actions.length - 1}`; show("builder"); revalidate();
  }

  // ---------------------------------------------------------------- test (preview) + results
  async function runTest(source) {
    if (!S.val || !S.val.ok) await revalidate();
    if (!S.val || !S.val.ok) { const p = $("#b-issues"); p.hidden = !S.val || !S.val.issues.length; $("#b-status").setAttribute("aria-expanded", String(!p.hidden)); toast("Fix the highlighted issues first, then test."); return; }
    const r = $("#results"); r.hidden = false; r.replaceChildren(h("h3", {}, "Testing…"), h("p", { class: "muted" }, "Running the read-only query. Nothing is changed.")); r.scrollIntoView({ behavior: "smooth", block: "nearest" });
    try { S.results = await api("/api/preview", { spec: S.spec, source }); renderResults(); renderCanvas(); r.scrollIntoView({ behavior: "smooth", block: "nearest" }); }
    catch (e) { S.results = null; r.replaceChildren(h("h3", {}, "Test failed"), h("p", { class: "bad" }, e.message)); }
  }
  $("#b-test").addEventListener("click", () => runTest("demo"));
  $("#b-test-live").addEventListener("click", () => runTest("live"));
  function renderResults() {
    const r = $("#results"), p = S.results; if (!r) return; r.replaceChildren();
    if (!p) { r.hidden = true; return; }
    r.hidden = false;
    r.append(h("h3", {}, `Test run · ${p.items} item${p.items === 1 ? "" : "s"} found`), h("p", { class: "muted" }, `${p.source === "demo" ? "Sample" : "Live"} data, read-only.`));
    if (p.rows.length) r.append(h("div", { class: "tbl" }, table(p.columns, p.rows.slice(0, 5).map((x) => p.columns.map((c) => x[c])))));
    if (p.rows.length > 5) r.append(h("p", { class: "muted" }, `…and ${p.rows.length - 5} more`));
    for (const a of p.actions) {
      r.append(h("div", { class: "res-act" }, h("div", { style: "display:flex;gap:8px;align-items:center;flex-wrap:wrap" }, appBadge(modOf(a.pipeline), 26), h("b", {}, `${a.index}. ${a.pipeline}`), tagEl(a.effect === "change" ? "Changes things" : "Creates / notifies", a.effect), tagEl(a.gated ? "after your approval" : "runs automatically", a.gated ? "change" : ""), h("span", { class: "muted" }, `× ${a.calls.length}`)),
        a.calls.length ? h("pre", { class: "code" }, JSON.stringify(a.calls[0], null, 1) + (a.calls.length > 1 ? `\n… and ${a.calls.length - 1} more` : "")) : null));
    }
    r.append(h("div", { class: "safe" }, ic("shield"), `${p.changes} change${p.changes === 1 ? "" : "s"} would be requested, and 0 have been made. This was only a preview.`));
  }
  function table(headers, rows) {
    const t = h("table", { class: "t" }, h("tr", {}, ...headers.map((x) => h("th", {}, x))));
    rows.forEach((r) => t.append(h("tr", {}, ...r.map((c) => h("td", {}, c == null ? "" : String(c))))));
    return t;
  }

  // ---------------------------------------------------------------- save / yaml
  $("#b-save").addEventListener("click", async () => {
    if (!S.val || !S.val.ok) { await revalidate(); if (!S.val || !S.val.ok) { toast("Fix the highlighted issues before saving."); $("#b-issues").hidden = false; return; } }
    try { const r = await api("/api/mods", { spec: S.spec, force: false }); toast(`Saved ${r.name}. Deploy it from My automations.`); }
    catch (e) { if (/already exists/.test(e.message) && confirm(`${e.message}\nOverwrite it?`)) { const r = await api("/api/mods", { spec: S.spec, force: true }); toast(`Overwrote ${r.name}`); } else toast(e.message, 7000); }
  });
  const dlg = $("#yaml-dlg");
  $("#b-yaml").addEventListener("click", async () => {
    $("#yaml-note").textContent = "This is the whole automation. Edit it and choose Apply, or copy it to keep in version control.";
    $("#yaml-text").value = S.val && S.val.yaml ? S.val.yaml : "# Finish the steps and the YAML appears here.";
    if (typeof dlg.showModal === "function") dlg.showModal(); else dlg.setAttribute("open", "");
  });
  $("#yaml-x").addEventListener("click", (e) => { e.preventDefault(); dlg.close(); });
  $("#yaml-copy").addEventListener("click", async () => { try { await navigator.clipboard.writeText($("#yaml-text").value); toast("Copied"); } catch (_) { toast("Select the text and copy it."); } });
  $("#yaml-apply").addEventListener("click", async () => {
    try { const v = await api("/api/validate", { yaml: $("#yaml-text").value }); if (!v.spec) throw new Error((v.issues[0] && v.issues[0].message) || "not a valid spec"); dlg.close(); await loadSpec(v.spec, { lock: true }); toast("Applied"); }
    catch (e) { $("#yaml-note").textContent = e.message; }
  });

  // ---------------------------------------------------------------- explore
  function card(name, desc, effect, load, extra) {
    const c = h("div", { class: "res" }), det = h("div", { class: "detail" });
    const b = h("button", { class: "head", "aria-expanded": "false" }, h("div", { class: "nm" }, name), h("div", { class: "ds" }, desc || ""), effect ? h("div", { class: "ds" }, tagEl(effect === "change" ? "Changes things" : effect === "notify" ? "Creates / notifies" : "Read-only", effect)) : null);
    b.addEventListener("click", async () => { const open = c.classList.toggle("open"); b.setAttribute("aria-expanded", String(open)); if (open && !det.childElementCount) { try { det.append(await load()); if (extra) det.append(extra()); } catch (e) { det.append(h("div", { class: "bad" }, e.message)); } } });
    c.append(b, det); return c;
  }
  const tableDetail = (n) => async () => { const d = await api(`/api/table/${encodeURIComponent(n)}`); return h("div", {}, table(["column", "type", "description"], (d.columns || []).map((c) => [c.name, c.type, (c.description || "").slice(0, 90)]))); };
  const pipeDetail = (n) => async () => { const d = await api(`/api/pipeline/${encodeURIComponent(n)}`); return h("div", {}, table(["param", "type", "required", "description"], (d.params || []).map((p) => [p.name, p.type, p.required ? "yes" : "", (p.description || "").slice(0, 80)])), h("pre", { class: "code" }, d.usage || "")); };
  async function runSearch() {
    const q = $("#q").value.trim(), out = $("#found"); out.replaceChildren(); if (!q) return;
    let r; try { r = await api(`/api/search?q=${encodeURIComponent(q)}`); } catch (e) { out.append(h("div", { class: "bad" }, e.message)); return; }
    const left = h("div", { class: "col" }, h("h4", {}, "Data · Steampipe tables")), right = h("div", { class: "col" }, h("h4", {}, "Actions · Flowpipe pipelines"));
    r.tables.forEach((t) => left.append(card(t.table, t.description, null, tableDetail(t.table), () => h("div", { class: "acts" }, h("button", { class: "btn primary sm", onclick: async () => { await useTableFromExplore(t.table); } }, "Start a query from this table")))));
    if (!r.tables.length) left.append(h("div", { class: "muted" }, "No matching tables."));
    r.actions.forEach((a) => { right.append(h("div", { class: "muted", style: "margin:6px 0" }, `for: ${a.clause}`)); a.pipelines.forEach((p) => right.append(card(p.pipeline, p.description, p.effect, pipeDetail(p.pipeline), () => h("div", { class: "acts" }, h("button", { class: "btn primary sm", onclick: () => addAction(p.pipeline) }, "Add as an action"))))); if (!a.pipelines.length) right.append(h("div", { class: "muted" }, "No matching actions.")); });
    out.append(h("div", { class: "cols2" }, left, right));
  }
  async function useTableFromExplore(name) {
    const d = await api(`/api/table/${encodeURIComponent(name)}`), c = (d.columns || []).slice(0, 6).map((x) => x.name);
    S.spec.detect.sql = `select\n  ${c.join(",\n  ")}\nfrom ${name}`; S.sel = "find"; show("builder"); revalidate();
  }
  $("#q").addEventListener("input", debounce(runSearch, 200));

  // ---------------------------------------------------------------- my automations (local only)
  async function loadMods() {
    const box = $("#modlist"); box.replaceChildren();
    let mods; try { mods = await api("/api/mods"); } catch (e) { box.append(h("div", { class: "bad" }, e.message)); return; }
    if (!mods.length) box.append(h("div", { class: "empty" }, "Nothing saved yet. Build one and choose Save."));
    mods.forEach((m) => box.append(modCard(m)));
  }
  function modCard(m) {
    const c = h("div", { class: "card" }), log = h("div", { class: "sp" }), acts = h("div", { class: "row sp" });
    c.append(h("div", { class: "row" }, h("b", {}, m.title), h("span", { class: "muted mono" }, m.name), h("span", { class: "grow" }), m.deployed ? h("span", { class: "ok" }, `deployed :${m.port}`) : h("span", { class: "muted" }, "not deployed")),
      h("div", { class: "muted" }, `spec hash ${m.hash} · ${m.trigger}` + (m.gated.length ? ` · you approve before: ${m.gated.join(", ")}` : " · no approval step")));
    acts.append(h("button", { class: "btn ghost sm", onclick: async () => { try { const r = await api(`/api/mods/${m.name}`); await loadSpec(r.spec); } catch (e) { toast(e.message); } } }, "Open in builder"));
    if (!m.deployed) {
      const cb = h("input", { type: "checkbox" }), go = h("button", { class: "btn primary sm", disabled: true }, "Deploy");
      cb.addEventListener("change", () => { go.disabled = !cb.checked; });
      go.addEventListener("click", async () => { go.disabled = true; go.textContent = "Deploying…"; try { await api(`/api/mods/${m.name}/deploy`, { spec_hash: m.hash, enable_schedule: false }); toast("Deployed"); loadMods(); } catch (e) { toast(e.message, 8000); go.textContent = "Deploy"; go.disabled = false; } });
      acts.append(h("label", { class: "row" }, cb, h("span", {}, `I reviewed this spec (hash ${m.hash})`)), go);
    } else {
      const run = h("button", { class: "btn primary sm" }, "Run now"), stop = h("button", { class: "btn ghost sm" }, "Stop");
      run.addEventListener("click", async () => { run.disabled = true; try { showRun(log, m, await api(`/api/mods/${m.name}/run`, {})); } catch (e) { toast(e.message, 8000); } run.disabled = false; });
      stop.addEventListener("click", async () => { try { await api(`/api/mods/${m.name}/undeploy`, {}); loadMods(); } catch (e) { toast(e.message); } });
      acts.append(run, stop);
    }
    acts.append(h("button", { class: "btn ghost sm", onclick: async () => { try { const ev = await api(`/api/mods/${m.name}/audit`); log.replaceChildren(h("div", { class: "tbl" }, table(["at", "actor", "kind", "spec_hash", "detail"], ev.map((e) => [e.at, e.actor, e.kind, e.spec_hash, e.detail])))); } catch (e) { toast(e.message); } } }, "Audit log"));
    c.append(acts, log); return c;
  }
  function showRun(log, m, s) {
    log.replaceChildren(); const d = h("div", {}, h("div", { class: "mono" }, `${s.execution_id}: `), h("b", { class: s.status === "failed" ? "bad" : "ok" }, s.status));
    if (s.error) d.append(h("div", { class: "bad" }, s.error));
    if (s.status === "waiting") {
      const yes = h("button", { class: "btn danger sm" }, "Approve"), no = h("button", { class: "btn ghost sm" }, "Skip"), answer = (choice) => async () => { yes.disabled = no.disabled = true; try { showRun(log, m, await api(`/api/mods/${m.name}/approve`, { execution: s.execution_id, choice })); } catch (e) { toast(e.message, 8000); } };
      yes.addEventListener("click", answer("approve")); no.addEventListener("click", answer("skip"));
      d.append(h("p", {}, "Waiting for your approval of the gated actions."), h("div", { class: "row" }, yes, no));
    } else if (s.outputs && Object.keys(s.outputs).length) d.append(h("pre", { class: "code" }, JSON.stringify(s.outputs, null, 1)));
    log.append(d);
  }

  // ---------------------------------------------------------------- boot
  (async () => {
    try { meta = await api("/api/meta"); } catch (e) { document.body.prepend(h("div", { class: "banner" }, `Cannot reach the opslens API: ${e.message}`)); return; }
    const demo = meta.mode === "demo";
    $("#badge").textContent = demo ? "public demo · sample data" : `local · v${meta.version}`; $("#badge").classList.toggle("demo", demo);
    if (demo) { const b = $("#banner"); b.hidden = false; b.textContent = "This is a public demo on sample data. Nothing here can reach a cloud account, deploy, or change anything."; $("#getit").hidden = false; }
    else $("#tab-mine").hidden = false;
    try { S.packs = await api("/api/packs"); } catch (e) { toast(`Could not load templates: ${e.message}`, 7000); }
    renderHome();
    const qs = new URLSearchParams(location.search), q = qs.get("q"), pk = qs.get("pack"), view = qs.get("view") || ({ find: "explore", build: "builder", mods: "mine" })[qs.get("tab")] || "home";
    if (q) { $("#q").value = q; runSearch(); }
    if (pk) { await loadPack(pk); if (qs.get("select")) select(qs.get("select")); if (qs.get("test")) await runTest("demo"); return; }
    show(VIEWS.includes(view) && !(view === "mine" && demo) ? view : "home", false);
    if (view === "builder" && !S.spec.actions.length && S.sel === null) { S.sel = "find"; renderPanel(); }
  })();
})();
