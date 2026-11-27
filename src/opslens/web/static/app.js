/* opslens app UI. All dynamic text goes through textContent (never innerHTML). */
(() => {
  "use strict";
  const $ = (s, el = document) => el.querySelector(s);
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text != null) e.textContent = text; return e; };
  let meta = null;

  async function api(path, body, method) {
    const opt = { method: method || (body === undefined ? "GET" : "POST"), headers: {} };
    if (body !== undefined) { opt.headers["Content-Type"] = "application/json"; opt.body = JSON.stringify(body); }
    if (opt.method !== "GET") opt.headers["X-Opslens-Token"] = meta ? meta.token : "";
    const r = await fetch(path, opt);
    let data = null; try { data = await r.json(); } catch (_) { /* empty */ }
    if (!r.ok) throw new Error((data && data.detail) || `${r.status} ${r.statusText}`);
    return data;
  }
  function toast(msg, ms = 3500) { const t = el("div", "toast", msg); t.setAttribute("role", "status"); document.body.append(t); setTimeout(() => t.remove(), ms); }
  const tag = (txt, kind) => el("span", `tag ${kind || ""}`, txt);
  const debounce = (fn, ms) => { let t; return (...a) => { clearTimeout(t); t = setTimeout(() => fn(...a), ms); }; };

  // ---------------------------------------------------------------- tabs
  function show(tab) {
    for (const b of document.querySelectorAll(".tab")) b.setAttribute("aria-selected", String(b.dataset.tab === tab));
    for (const s of ["find", "build", "mods"]) $(`#p-${s}`).hidden = s !== tab;
    if (tab === "mods") loadMods();
  }
  for (const b of document.querySelectorAll(".tab")) b.addEventListener("click", () => show(b.dataset.tab));

  // ---------------------------------------------------------------- find
  function table(headers, rows) {
    const t = el("table", "t"), h = el("tr");
    headers.forEach((x) => h.append(el("th", "", x))); t.append(h);
    rows.forEach((r) => { const tr = el("tr"); r.forEach((c) => tr.append(el("td", "", c == null ? "" : String(c)))); t.append(tr); });
    return t;
  }
  function card(name, desc, effect, load) {
    const c = el("div", "res"), b = el("button"), det = el("div", "detail");
    b.setAttribute("aria-expanded", "false");
    b.append(el("div", "nm", name), el("div", "ds", desc || ""));
    if (effect) { const m = el("div", "ds"); m.append(tag(effect, effect)); b.append(m); }
    b.addEventListener("click", async () => {
      const open = c.classList.toggle("open"); b.setAttribute("aria-expanded", String(open));
      if (open && !det.childElementCount) { try { det.append(await load()); } catch (e) { det.append(el("div", "bad", e.message)); } }
    });
    c.append(b, det); return c;
  }
  const tableDetail = (n) => async () => {
    const d = await api(`/api/table/${encodeURIComponent(n)}`);
    const w = el("div"); w.append(table(["column", "type", "description"], (d.columns || []).map((c) => [c.name, c.type, (c.description || "").slice(0, 90)])));
    return w;
  };
  const pipeDetail = (n) => async () => {
    const d = await api(`/api/pipeline/${encodeURIComponent(n)}`);
    const w = el("div");
    w.append(table(["param", "type", "required", "description"], (d.params || []).map((p) => [p.name, p.type, p.required ? "yes" : "", (p.description || "").slice(0, 80)])), el("pre", "code", d.usage || ""));
    return w;
  };
  async function runSearch() {
    const q = $("#q").value.trim(), out = $("#found"); out.replaceChildren();
    if (!q) return;
    let r; try { r = await api(`/api/search?q=${encodeURIComponent(q)}`); } catch (e) { out.append(el("div", "bad", e.message)); return; }
    const g = el("div", "cols2"), left = el("div", "col"), right = el("div", "col");
    left.append(el("h4", "", "Data · Steampipe tables"));
    r.tables.forEach((t) => left.append(card(t.table, t.description, null, tableDetail(t.table))));
    if (!r.tables.length) left.append(el("div", "muted", "No matching tables."));
    right.append(el("h4", "", "Actions · Flowpipe pipelines"));
    r.actions.forEach((a) => {
      right.append(el("div", "muted", `for: ${a.clause}`));
      a.pipelines.forEach((p) => right.append(card(p.pipeline, p.description, p.effect, pipeDetail(p.pipeline))));
      if (!a.pipelines.length) right.append(el("div", "muted", "No matching pipelines."));
    });
    g.append(left, right); out.append(g);
  }
  $("#q").addEventListener("input", debounce(runSearch, 200));

  // ---------------------------------------------------------------- build
  let lastHash = null, lastOk = false;
  function renderResult(v) {
    const box = $("#result"); box.replaceChildren();
    const head = el("div", "row"); head.append(el("span", v.ok ? "ok" : "bad", v.ok ? "✓ valid" : "✗ has errors"));
    if (v.hash) head.append(el("span", "muted", `spec hash ${v.hash}`));
    box.append(head);
    v.issues.forEach((i) => { const d = el("div", `issue ${i.level}`); d.append(el("b", "", `${i.level} `), el("span", "mono", i.code + " "), el("span", "", (i.where ? i.where + ": " : "") + i.message)); box.append(d); });
    if (v.explain && v.explain.length) { const ul = el("ul", "plain"); v.explain.forEach((x) => ul.append(el("li", "", x))); box.append(el("h4", "muted", "What it does"), ul); }
    if (v.gated && v.gated.length) { const p = el("div", "sp"); p.append(el("span", "muted", "Waits for approval: ")); v.gated.forEach((g) => { p.append(tag(g, "change"), document.createTextNode(" ")); }); box.append(p); }
  }
  async function validate() {
    const text = $("#spec").value;
    if (!text.trim()) { $("#actions").hidden = true; return; }
    try {
      const v = await api("/api/validate", { yaml: text });
      lastOk = v.ok; lastHash = v.hash; renderResult(v);
      $("#actions").hidden = false; $("#prev").disabled = !v.ok; $("#save").disabled = !v.ok; $("#prevlive").disabled = !v.ok;
    } catch (e) {
      lastOk = false; $("#result").replaceChildren(el("span", "bad", e.message)); $("#actions").hidden = true;
    }
  }
  $("#spec").addEventListener("input", debounce(validate, 400));

  async function doPreview(source) {
    const out = $("#preview"); out.replaceChildren(el("span", "muted", "Running read-only query…"));
    let p; try { p = await api("/api/preview", { yaml: $("#spec").value, source }); } catch (e) { out.replaceChildren(el("span", "bad", e.message)); return; }
    out.replaceChildren();
    const c = el("div", "card");
    c.append(el("div", "", `${p.items} item${p.items === 1 ? "" : "s"} found (${p.source} data).`));
    if (p.rows.length) c.append(table(p.columns, p.rows.slice(0, 8).map((r) => p.columns.map((k) => r[k]))));
    p.actions.forEach((a) => {
      const h = el("div", "sp"); h.append(el("b", "", `${a.index}. ${a.pipeline} `), tag(a.effect, a.effect), el("span", "muted", a.gated ? "  runs after approval" : "  runs automatically"), el("span", "muted", `  × ${a.calls.length}`));
      c.append(h);
      if (a.calls.length) c.append(el("pre", "code", JSON.stringify(a.calls[0], null, 1) + (a.calls.length > 1 ? `\n… and ${a.calls.length - 1} more` : "")));
    });
    c.append(el("div", `sp ${p.changes ? "bad" : "ok"}`, `${p.changes} state change(s) would be requested; 0 have been made (preview only).`));
    out.append(c);
  }
  $("#prev").addEventListener("click", () => doPreview("demo"));
  $("#prevlive").addEventListener("click", () => doPreview("live"));
  $("#save").addEventListener("click", async () => {
    try { const r = await api("/api/mods", { yaml: $("#spec").value, force: false }); toast(`Saved ${r.name} (hash ${r.hash})`); }
    catch (e) {
      if (/already exists/.test(e.message) && confirm(`${e.message}\nOverwrite it?`)) { const r = await api("/api/mods", { yaml: $("#spec").value, force: true }); toast(`Overwrote ${r.name}`); }
      else toast(e.message, 6000);
    }
  });
  $("#pack").addEventListener("change", async (ev) => {
    if (!ev.target.value) return;
    const r = await api(`/api/packs/${ev.target.value}`); $("#spec").value = r.yaml; validate();
  });
  $("#gen").addEventListener("click", async () => {
    const ask = $("#ask").value.trim(); if (!ask) return;
    $("#gen").disabled = true; $("#genmsg").textContent = `Asking ${meta.provider}…`;
    try { const r = await api("/api/generate", { requirement: ask }); $("#spec").value = r.yaml; $("#genmsg").textContent = `AI-drafted (${r.model}, ${r.attempts} attempt${r.attempts > 1 ? "s" : ""}). Read it before you trust it.`; validate(); }
    catch (e) { $("#genmsg").textContent = e.message; }
    finally { $("#gen").disabled = false; }
  });

  // ---------------------------------------------------------------- mods (local only)
  async function loadMods() {
    const box = $("#modlist"); box.replaceChildren();
    let mods; try { mods = await api("/api/mods"); } catch (e) { box.append(el("div", "bad", e.message)); return; }
    if (!mods.length) box.append(el("div", "muted", "Nothing saved yet. Build a spec and choose “Save to workspace”."));
    mods.forEach((m) => box.append(modCard(m)));
  }
  function modCard(m) {
    const c = el("div", "card sp"), head = el("div", "row");
    head.append(el("b", "", m.title), el("span", "muted mono", m.name), el("span", "grow"), m.deployed ? el("span", "ok", `deployed :${m.port}`) : el("span", "muted", "not deployed"));
    c.append(head, el("div", "muted", `spec hash ${m.hash} · ${m.trigger}` + (m.gated.length ? ` · approval before: ${m.gated.join(", ")}` : " · no approval step")));
    const acts = el("div", "row sp"), log = el("div", "sp");
    if (!m.deployed) {
      const lab = el("label", "row"), cb = el("input"); cb.type = "checkbox";
      lab.append(cb, el("span", "", `I reviewed this spec (hash ${m.hash})`));
      const go = el("button", "pill primary sm", "Deploy"); go.disabled = true; cb.addEventListener("change", () => { go.disabled = !cb.checked; });
      go.addEventListener("click", async () => { go.disabled = true; go.textContent = "Deploying…"; try { await api(`/api/mods/${m.name}/deploy`, { spec_hash: m.hash, enable_schedule: false }); toast("Deployed"); loadMods(); } catch (e) { toast(e.message, 7000); go.textContent = "Deploy"; go.disabled = false; } });
      acts.append(lab, go);
    } else {
      const run = el("button", "pill primary sm", "Run now"), stop = el("button", "pill ghost sm", "Stop");
      run.addEventListener("click", async () => { run.disabled = true; try { showRun(log, m, await api(`/api/mods/${m.name}/run`, {})); } catch (e) { toast(e.message, 7000); } run.disabled = false; });
      stop.addEventListener("click", async () => { try { await api(`/api/mods/${m.name}/undeploy`, {}); loadMods(); } catch (e) { toast(e.message); } });
      acts.append(run, stop);
    }
    const au = el("button", "pill ghost sm", "Audit log");
    au.addEventListener("click", async () => { try { const ev = await api(`/api/mods/${m.name}/audit`); log.replaceChildren(table(["at", "actor", "kind", "spec_hash", "detail"], ev.map((e) => [e.at, e.actor, e.kind, e.spec_hash, e.detail]))); } catch (e) { toast(e.message); } });
    acts.append(au); c.append(acts, log); return c;
  }
  function showRun(log, m, s) {
    log.replaceChildren(); const d = el("div", "card");
    d.append(el("div", "", `${s.execution_id}: `), el("b", s.status === "failed" ? "bad" : "ok", s.status));
    if (s.error) d.append(el("div", "bad", s.error));
    if (s.status === "waiting") {
      d.append(el("div", "sp", "Waiting for your approval of the gated actions."));
      const r = el("div", "row sp"), yes = el("button", "pill danger sm", "Approve"), no = el("button", "pill ghost sm", "Skip");
      const answer = (choice) => async () => { yes.disabled = no.disabled = true; try { showRun(log, m, await api(`/api/mods/${m.name}/approve`, { execution: s.execution_id, choice })); } catch (e) { toast(e.message, 7000); } };
      yes.addEventListener("click", answer("approve")); no.addEventListener("click", answer("skip")); r.append(yes, no); d.append(r);
    } else if (s.outputs && Object.keys(s.outputs).length) d.append(el("pre", "code", JSON.stringify(s.outputs, null, 1)));
    log.append(d);
  }

  // ---------------------------------------------------------------- boot
  (async () => {
    try { meta = await api("/api/meta"); } catch (e) { document.body.prepend(el("div", "banner", `Cannot reach the opslens API: ${e.message}`)); return; }
    const demo = meta.mode === "demo";
    $("#badge").textContent = demo ? "public demo · sample data" : `local · v${meta.version}`; $("#badge").classList.toggle("demo", demo);
    if (demo) { const b = $("#banner"); b.hidden = false; b.textContent = "This is a public demo on sample data. Nothing here can reach a cloud account, deploy, or change anything. Install opslens to use it for real."; }
    else { $("#tab-mods").hidden = false; $("#save").hidden = false; $("#prevlive").hidden = false; }
    if (meta.ai) $("#askbox").hidden = false;
    try { (await api("/api/packs")).forEach((p) => { const o = el("option", "", `${p.pack}: ${p.title}`); o.value = p.pack; $("#pack").append(o); }); } catch (_) { /* optional */ }
    const qs = new URLSearchParams(location.search), q = qs.get("q");
    if (q) { $("#q").value = q; runSearch(); }
    const tab = qs.get("tab"); if (tab === "build" || (tab === "mods" && !demo)) show(tab);
    const pk = qs.get("pack"); if (pk) { $("#pack").value = pk; $("#pack").dispatchEvent(new Event("change")); }
  })();
})();
