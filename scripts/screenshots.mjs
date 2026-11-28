// Regenerate the product screenshots used on the website and in the docs.
//   opslens serve --mode demo --port 8078 &      # sample data only, no cloud needed
//   node scripts/screenshots.mjs [http://127.0.0.1:8078/] [website/static/screens]
// Needs Node 22+ (built-in WebSocket) and Google Chrome; it drives Chrome over the DevTools protocol, no npm packages.
// Output is WebP (via `cwebp`) when available, else PNG.
import { spawn, execFileSync } from "node:child_process";
import { writeFileSync, mkdirSync, rmSync } from "node:fs";
import { join } from "node:path";

const BASE = process.argv[2] || "http://127.0.0.1:8078/";
const OUT = process.argv[3] || "website/static/screens";
const CHROME = process.env.CHROME || "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome";
mkdirSync(OUT, { recursive: true });
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

async function open({ width, height, dark = false, port }) {
  const profile = `/tmp/opslens-shots-${port}`;
  const proc = spawn(CHROME, ["--headless=new", `--remote-debugging-port=${port}`, "--disable-gpu", "--hide-scrollbars", `--user-data-dir=${profile}`, "about:blank"], { stdio: "ignore" });
  let page; for (let i = 0; i < 80 && !page; i++) { try { page = (await (await fetch(`http://127.0.0.1:${port}/json`)).json()).find((t) => t.type === "page"); } catch (_) { /* starting */ } if (!page) await sleep(250); }
  const ws = new WebSocket(page.webSocketDebuggerUrl); await new Promise((r) => ws.addEventListener("open", r));
  let id = 0; const pend = new Map();
  ws.addEventListener("message", (e) => { const m = JSON.parse(e.data); if (m.id && pend.has(m.id)) { pend.get(m.id)(m); pend.delete(m.id); } });
  const send = (method, params = {}) => new Promise((res) => { const i = ++id; pend.set(i, res); ws.send(JSON.stringify({ id: i, method, params })); });
  await send("Page.enable"); await send("Runtime.enable");
  await send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1.5, mobile: false });
  await send("Emulation.setEmulatedMedia", { features: [{ name: "prefers-color-scheme", value: dark ? "dark" : "light" }] });
  const ev = async (expr) => { const r = await send("Runtime.evaluate", { expression: expr, awaitPromise: true, returnByValue: true }); if (r.result.exceptionDetails) throw new Error(r.result.exceptionDetails.exception?.description || "eval failed"); return r.result.result.value; };
  return {
    ev, sleep,
    async go(path, wait = 2500) { await send("Page.navigate", { url: BASE + path }); await sleep(wait); },
    click: (sel) => ev(`document.querySelector(${JSON.stringify(sel)}).click()`),
    type: (sel, text) => ev(`(()=>{const i=document.querySelector(${JSON.stringify(sel)});i.value=${JSON.stringify(text)};i.dispatchEvent(new Event('input',{bubbles:true}))})()`),
    async shot(name) {
      const r = await send("Page.captureScreenshot", { format: "png" }); const png = join(OUT, `${name}.png`);
      writeFileSync(png, Buffer.from(r.result.data, "base64"));
      try { execFileSync("cwebp", ["-quiet", "-q", "84", png, "-o", join(OUT, `${name}.webp`)]); rmSync(png); } catch (_) { /* keep the PNG */ }
      console.log("wrote", name);
    },
    async close() { ws.close(); proc.kill(); },
  };
}

const PACK = "?pack=finops-cleanup/unattached-volumes";
let b = await open({ width: 1360, height: 1060, port: 9441 });
await b.go(""); await b.shot("templates");
await b.go(`${PACK}&select=a0`, 3200); await b.sleep(300); await b.shot("builder");
await b.go(`${PACK}&select=a1`, 3200); await b.shot("approval");
await b.close();

b = await open({ width: 1360, height: 1500, port: 9442 });
await b.go(`${PACK}&test=1`, 4500); await b.shot("test");
await b.close();

b = await open({ width: 1360, height: 900, port: 9443 });
await b.go("?view=builder", 2500); await b.click(".tpl.blank").catch(() => {});
await b.go("", 2000); await b.click(".tpl.blank"); await b.sleep(600);
await b.type("#panel input[type=search]", "ebs volume"); await b.sleep(1500); await b.shot("find");
await b.type("textarea.sql", "select volume_id, region, size from aws_ebs_volume where state = 'available'"); await b.sleep(900);
await b.click(".add"); await b.sleep(900); await b.type("#panel input[type=search]", "open a jira ticket"); await b.sleep(1500); await b.shot("picker");
await b.close();

b = await open({ width: 1360, height: 900, port: 9444 });
await b.go(`${PACK}`, 3000); await b.click("#b-yaml"); await b.sleep(700); await b.shot("yaml");
await b.go("?view=explore&q=unattached ebs volumes then open a jira ticket", 3000);
await b.ev(`document.querySelectorAll('.res > button.head').forEach((x,i)=>{ if(i===0) x.click(); })`); await b.sleep(1200); await b.shot("explore");
await b.close();

b = await open({ width: 1360, height: 900, dark: true, port: 9445 });
await b.go("?pack=governance/tag-enforcement&select=a0", 3500); await b.shot("dark");
await b.close();

b = await open({ width: 1360, height: 900, port: 9446 });
await b.go("?pack=incident/incident-copilot", 3500); await b.shot("incident");
await b.close();
