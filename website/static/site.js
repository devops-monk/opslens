// opslens site behaviour. No dependencies. Every dynamic string is set as text.
(() => {
  "use strict";
  const $ = (s, r = document) => r.querySelector(s), $$ = (s, r = document) => [...r.querySelectorAll(s)];

  // theme: light / dark / system. The saved choice is applied early by theme.js.
  const root = document.documentElement;
  const dark = () => root.getAttribute("data-theme") === "dark" || (!root.getAttribute("data-theme") && matchMedia("(prefers-color-scheme: dark)").matches);
  $$(".theme-btn").forEach((b) => b.addEventListener("click", () => {
    const next = dark() ? "light" : "dark"; root.setAttribute("data-theme", next);
    try { localStorage.setItem("opslens-theme", next); } catch (_) { /* storage blocked */ }
  }));

  // mobile menu
  const mb = $(".menu-btn"), nav = $("#nav");
  if (mb && nav) { mb.addEventListener("click", () => { const o = nav.classList.toggle("open"); mb.setAttribute("aria-expanded", String(o)); });
    $$("#nav a").forEach((a) => a.addEventListener("click", () => { nav.classList.remove("open"); mb.setAttribute("aria-expanded", "false"); })); }

  // copy buttons: the hero command, and one on every code block that is long enough to want it
  async function copy(btn, text) {
    try { await navigator.clipboard.writeText(text); } catch (_) { const t = document.createElement("textarea"); t.value = text; document.body.append(t); t.select(); try { document.execCommand("copy"); } catch (e) { /* ignore */ } t.remove(); }
    btn.classList.add("done"); setTimeout(() => btn.classList.remove("done"), 1400);
  }
  $$("button.copy[data-copy]").forEach((b) => b.addEventListener("click", () => copy(b, b.dataset.copy)));
  $$("pre.code:not(.term)").forEach((pre) => {
    if (pre.closest(".cmd")) return;
    const b = document.createElement("button"); b.type = "button"; b.className = "copy"; b.setAttribute("aria-label", "Copy code");
    b.style.cssText = "position:absolute;top:8px;right:8px;width:30px;height:30px;opacity:.85";
    const svg = $(".cmd .copy svg"); if (svg) b.append(svg.cloneNode(true)); else b.textContent = "Copy";
    b.addEventListener("click", () => copy(b, pre.innerText.replace(/\n$/, "")));
    pre.append(b);
  });

  // install tabs
  $$("[data-tabs]").forEach((box) => {
    const tabs = $$('[role="tab"]', box);
    const pick = (t) => tabs.forEach((x) => { const on = x === t; x.setAttribute("aria-selected", String(on)); $("#" + x.getAttribute("aria-controls")).hidden = !on; });
    tabs.forEach((t) => t.addEventListener("click", () => pick(t)));
  });

  // docs: filter the sidebar, collapse it on small screens, highlight the section in view
  const f = $(".doc-filter input");
  if (f) f.addEventListener("input", () => {
    const q = f.value.trim().toLowerCase(); let any = false;
    $$(".docgroup").forEach((g) => { let n = 0; $$("li", g).forEach((li) => { const show = !q || li.textContent.toLowerCase().includes(q); li.hidden = !show; if (show) n++; }); g.hidden = n === 0; any = any || n > 0; });
    const e = $(".doc-empty"); if (e) e.hidden = any;
  });
  const dt = $(".docnav-toggle"), dn = $("#docnav");
  if (dt && dn) dt.addEventListener("click", () => { const o = dn.classList.toggle("open"); dt.setAttribute("aria-expanded", String(o)); });
  const links = $$(".toc a[href^='#']");
  if (links.length && "IntersectionObserver" in window) {
    const map = new Map(links.map((a) => [a.getAttribute("href").slice(1), a]));
    const io = new IntersectionObserver((es) => { es.forEach((e) => { if (e.isIntersecting) { links.forEach((l) => l.classList.remove("on")); const a = map.get(e.target.id); if (a) a.classList.add("on"); } }); }, { rootMargin: "-80px 0px -70% 0px" });
    $$(".prose h2[id], .prose h3[id]").forEach((h) => io.observe(h));
  }
  // the current page, in view inside the sidebar
  const cur = $(".docgroup a[aria-current='page']"); if (cur && cur.scrollIntoView && $(".sidebar")) { const s = $(".sidebar"); if (s.scrollHeight > s.clientHeight) cur.scrollIntoView({ block: "center" }); }
})();
