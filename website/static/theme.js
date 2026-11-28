// Runs before first paint so there is no flash: apply the saved theme, if any.
try { var t = localStorage.getItem("opslens-theme"); if (t === "light" || t === "dark") document.documentElement.setAttribute("data-theme", t); } catch (e) { /* storage blocked: follow the system */ }
