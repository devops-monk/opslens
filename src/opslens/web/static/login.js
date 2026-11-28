// Sign-in form. Messages are set as text; nothing from the server is rendered as HTML.
(() => {
  "use strict";
  const f = document.getElementById("f"), err = document.getElementById("err"), go = document.getElementById("go");
  try { const u = localStorage.getItem("opslens-user"); if (u) document.getElementById("user").value = u; } catch (_) { /* storage blocked */ }
  f.addEventListener("submit", async (e) => {
    e.preventDefault(); err.hidden = true; go.disabled = true;
    const user = document.getElementById("user").value.trim(), password = document.getElementById("pw").value;
    try {
      const r = await fetch("api/login", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ user, password }) });
      const d = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof d.detail === "string" ? d.detail : `Sign-in failed (${r.status})`);
      try { localStorage.setItem("opslens-user", user); } catch (_) { /* ignore */ }
      location.href = "./";
    } catch (ex) { err.textContent = ex.message; err.hidden = false; go.disabled = false; document.getElementById("pw").select(); }
  });
})();
