"""Hand-built inline SVG diagrams for the Architecture page (C4 levels 1-3 and sequence diagrams).

No JavaScript and no external files, so they work under the site's strict CSP and follow the light/dark theme through CSS
classes defined in website/static/style.css (.dg-*). Coordinates are laid out by hand; keep text short so it fits its box.
"""

from __future__ import annotations

from html import escape

from markupsafe import Markup

MARKER = (
    '<defs><marker id="{id}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
    '<path d="M0 0L10 5L0 10z" class="dg-head"/></marker></defs>'
)


def _lines(text: str, x: float, y: float, cls: str, gap: float = 15) -> str:
    return "".join(f'<text x="{x}" y="{y + i * gap}" class="{cls}">{escape(t)}</text>' for i, t in enumerate(text.split("\n")))


class Svg:
    def __init__(self, w: int, h: int, name: str, title: str, desc: str):
        self.w, self.h, self.name = w, h, name
        self.parts: list[str] = []
        self.title, self.desc = title, desc

    def box(self, x, y, w, h, title, sub="", kind="system", tech=""):
        """kind: person | system | external | container | component | store."""
        r = 22 if kind == "person" else 10
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" class="dg-box dg-{kind}"/>')
        cy = y + 22
        on = " dg-on" if kind == "system" else ""
        self.parts.append(f'<text x="{x + w / 2}" y="{cy}" class="dg-title{on}" text-anchor="middle">{escape(title)}</text>')
        if tech:
            cy += 16
            self.parts.append(f'<text x="{x + w / 2}" y="{cy}" class="dg-tech{on}" text-anchor="middle">[{escape(tech)}]</text>')
        if sub:
            self.parts.append(_lines(sub, x + w / 2, cy + 18, f"dg-sub{on}\" text-anchor=\"middle", 14))

    def group(self, x, y, w, h, label, right=False):
        self.parts.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="14" class="dg-group"/>')
        tx, anchor = (x + w - 14, ' text-anchor="end"') if right else (x + 14, "")
        self.parts.append(f'<text x="{tx}" y="{y + 22}" class="dg-glabel"{anchor}>{escape(label)}</text>')

    def arrow(self, x1, y1, x2, y2, label="", dash=False, label_at=0.5, dx=0, dy=-6, anchor="middle", both=False):
        cls = "dg-arrow dg-dash" if dash else "dg-arrow"
        start = f' marker-start="url(#{self.name}-a)"' if both else ""
        self.parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" class="{cls}" marker-end="url(#{self.name}-a)"{start}/>')
        if label:
            lx, ly = x1 + (x2 - x1) * label_at + dx, y1 + (y2 - y1) * label_at + dy
            # a halo behind the text keeps it readable where it crosses a line
            self.parts.append(_lines(label, lx, ly, f'dg-halo" text-anchor="{anchor}', 13))
            self.parts.append(_lines(label, lx, ly, f'dg-lbl" text-anchor="{anchor}', 13))

    def render(self) -> Markup:
        body = "".join(self.parts)
        return Markup(
            f'<figure class="diagram"><svg viewBox="0 0 {self.w} {self.h}" role="img" aria-labelledby="{self.name}-t {self.name}-d" '
            f'xmlns="http://www.w3.org/2000/svg"><title id="{self.name}-t">{escape(self.title)}</title><desc id="{self.name}-d">'
            f"{escape(self.desc)}</desc>{MARKER.format(id=self.name + '-a')}{body}</svg><figcaption>{escape(self.title)}</figcaption></figure>"
        )


# ------------------------------------------------------------------ C4
def c4_context() -> Markup:
    s = Svg(940, 520, "c4ctx", "C4 level 1: system context",
            "A person uses opslens. opslens reads from Steampipe, acts through Flowpipe, and optionally asks an AI model for a draft.")
    s.box(370, 20, 200, 84, "Ops engineer", "describes the need,\nreviews, approves", "person")
    s.box(330, 200, 280, 110, "opslens", "turns a requirement into a reviewed,\nvalidated Flowpipe automation", "system", "software system")
    s.box(20, 380, 250, 100, "Steampipe", "SQL over AWS, GitLab, Jira,\nOpsgenie and Microsoft 365", "external", "read-only data")
    s.box(345, 380, 250, 100, "Flowpipe", "runs the pipelines, schedules,\nasks for approval", "external", "executes actions")
    s.box(670, 380, 250, 100, "Teams, Slack, Jira, AWS ...", "where tickets, messages and\nchanges land", "external", "your services")
    s.box(690, 200, 230, 100, "AI model (optional)", "drafts a spec from a sentence;\nsees catalog names only", "external", "any provider")
    s.arrow(470, 104, 470, 200, "describes, reviews,\napproves", label_at=0.35, dx=8, anchor="start", both=True)
    s.arrow(400, 310, 170, 380, "reads rows\n(read-only SQL)", dx=-6, anchor="end", dy=-4)
    s.arrow(470, 310, 470, 380, "deploys and runs", dx=8, anchor="start", dy=0)
    s.arrow(595, 430, 670, 430, "calls", dy=-8)
    s.arrow(610, 255, 690, 250, "draft request", dash=True, dy=-8)
    return s.render()


def c4_containers() -> Markup:
    s = Svg(980, 600, "c4con", "C4 level 2: containers",
            "Inside opslens: a command line and a web app share one Python core library and a local workspace. Steampipe and Flowpipe run as separate programs.")
    s.box(390, 14, 200, 70, "Ops engineer", "", "person")
    s.group(20, 110, 940, 290, "opslens (one Python package, Apache-2.0)", right=True)
    s.box(50, 150, 250, 100, "CLI", "search, query, preview,\ndeploy, approve, runs", "container", "Typer")
    s.box(365, 150, 250, 100, "Web app", "templates, builder, test panel,\nsign-in in team mode", "container", "FastAPI + static UI")
    s.box(680, 150, 250, 100, "AI planner (optional)", "prompt, call, validate,\nretry up to 3 times", "container", "provider adapters")
    s.box(50, 290, 565, 90, "Core library", "catalogs, spec, validation, SQL guard, renderer, preview,\nFlowpipe client, audit", "container", "Python")
    s.box(680, 290, 250, 90, "Workspace on disk", "spec.yaml and generated .fp\nfiles, audit log, run records", "store", "files")
    s.box(120, 460, 260, 110, "Steampipe service", "Postgres interface on :9193;\nplugins call the cloud APIs", "external", "separate program")
    s.box(430, 460, 260, 110, "Flowpipe server", "REST API on :7103; runs\npipelines and triggers", "external", "separate program")
    s.box(740, 460, 220, 110, "Your services", "AWS, GitLab, Jira, Opsgenie,\nTeams, Slack", "external", "APIs")
    s.arrow(450, 84, 175, 150, "terminal", dx=-4, anchor="end", dy=-4)
    s.arrow(490, 84, 490, 150, "browser", dx=8, anchor="start", dy=0)
    s.arrow(175, 250, 175, 290, "")
    s.arrow(490, 250, 490, 290, "")
    s.arrow(680, 215, 615, 215, "", dash=True)
    s.arrow(615, 335, 680, 335, "reads and writes")
    s.arrow(250, 380, 250, 460, "SQL over a\nPostgres connection", dx=8, anchor="start", dy=-12)
    s.arrow(560, 380, 560, 460, "deploy, run,\napprove (REST)", dx=8, anchor="start", dy=-12)
    s.arrow(690, 515, 740, 515, "")
    s.arrow(380, 515, 430, 515, "", dash=True)
    return s.render()


def c4_components() -> Markup:
    s = Svg(980, 640, "c4cmp", "C4 level 3: components of the core library",
            "The core library splits into catalogs, a spec model with validation and a deterministic renderer, a guarded SQL client, "
            "preview, a Flowpipe client, and the audit trail.")
    s.group(20, 20, 940, 600, "Core library (src/opslens)")
    s.box(50, 60, 260, 92, "Catalogs", "670 tables, 443 pipelines,\nbuilt offline from source", "component", "catalog/")
    s.box(360, 60, 260, 92, "Search", "plain words to the right\ntable and action", "component", "catalog/search")
    s.box(670, 60, 260, 92, "Packs", "32 curated, ready specs", "component", "packs/")
    s.box(50, 200, 260, 100, "Spec model", "typed YAML: trigger, query,\nactions, variables, hash", "component", "spec/model")
    s.box(360, 200, 260, 100, "Validator", "real columns, typed args,\nchanges must be gated", "component", "spec/check")
    s.box(670, 200, 260, 100, "Renderer", "deterministic HCL, escapes\nevery literal", "component", "spec/render")
    s.box(50, 350, 260, 100, "SQL guard", "single SELECT, allow-listed\ntables, timeout, row cap", "component", "sql/guard")
    s.box(360, 350, 260, 100, "SQL client", "live: Steampipe. demo: sample\ndata on SQLite", "component", "sql/client, demo/")
    s.box(670, 350, 260, 100, "Preview", "what a run would do,\nwith nothing sent", "component", "validate/preview")
    s.box(50, 500, 260, 100, "Flowpipe client", "deploy, run, approve,\nserver lifecycle", "component", "flowpipe/")
    s.box(360, 500, 260, 100, "Runs and audit", "append-only record of\ndeploy, run, approval", "component", "runs/")
    s.box(670, 500, 260, 100, "Config", "defaults, file, env, --set;\nsecrets from env only", "component", "config")
    s.arrow(310, 106, 360, 106, "")
    s.arrow(180, 152, 180, 200, "")
    s.arrow(310, 250, 360, 250, "")
    s.arrow(620, 250, 670, 250, "")
    s.arrow(490, 300, 490, 350, "")
    s.arrow(180, 300, 180, 350, "", dash=True)
    s.arrow(310, 400, 360, 400, "")
    s.arrow(620, 400, 670, 400, "", both=True)
    s.arrow(800, 300, 800, 350, "", dash=True)
    s.arrow(800, 450, 800, 500, "", dash=True)
    s.arrow(670, 550, 620, 550, "")
    s.arrow(360, 550, 310, 550, "", both=True)
    return s.render()


# ------------------------------------------------------------------ sequence diagrams
class Seq:
    def __init__(self, name: str, title: str, desc: str, actors: list[tuple[str, str]], rows: int, width: int = 940, top: int = 74):
        self.name, self.title, self.desc, self.actors = name, title, desc, actors
        self.w = width
        self.top = top
        self.step = 40
        self.h = top + rows * self.step + 30
        n = len(actors)
        pad = 80
        self.xs = [pad + i * (width - 2 * pad) / (n - 1) for i in range(n)]
        self.parts: list[str] = []
        self.y = top + 28
        for x, (name_, sub) in zip(self.xs, actors, strict=True):
            self.parts.append(f'<rect x="{x - 66}" y="12" width="132" height="{42 if sub else 34}" rx="8" class="dg-box dg-container"/>')
            self.parts.append(f'<text x="{x}" y="32" class="dg-title" text-anchor="middle">{escape(name_)}</text>')
            if sub:
                self.parts.append(f'<text x="{x}" y="47" class="dg-tech" text-anchor="middle">{escape(sub)}</text>')
            self.parts.append(f'<line x1="{x}" y1="{top - 6}" x2="{x}" y2="{self.h - 14}" class="dg-life"/>')

    def msg(self, a: int, b: int, text: str, dash=False, note=False):
        x1, x2, y = self.xs[a], self.xs[b], self.y
        if a == b:  # self call
            self.parts.append(f'<path d="M{x1} {y - 8} h26 v16 h-26" class="dg-arrow" fill="none" marker-end="url(#{self.name}-a)"/>')
            self.parts.append(f'<text x="{x1 + 34}" y="{y + 4}" class="dg-lbl" text-anchor="start">{escape(text)}</text>')
        else:
            cls = "dg-arrow dg-dash" if dash else "dg-arrow"
            self.parts.append(f'<line x1="{x1}" y1="{y}" x2="{x2}" y2="{y}" class="{cls}" marker-end="url(#{self.name}-a)"/>')
            self.parts.append(f'<text x="{(x1 + x2) / 2}" y="{y - 6}" class="dg-halo" text-anchor="middle">{escape(text)}</text>')
            self.parts.append(f'<text x="{(x1 + x2) / 2}" y="{y - 6}" class="dg-lbl" text-anchor="middle">{escape(text)}</text>')
        self.y += self.step

    def gate(self, text: str):
        """A highlighted band: the point where a human must act."""
        y = self.y - 22
        self.parts.append(f'<rect x="14" y="{y}" width="{self.w - 28}" height="30" rx="8" class="dg-gate"/>')
        self.parts.append(f'<text x="{self.w / 2}" y="{y + 20}" class="dg-gtext" text-anchor="middle">{escape(text)}</text>')
        self.y += self.step - 4

    def render(self) -> Markup:
        return Markup(
            f'<figure class="diagram"><svg viewBox="0 0 {self.w} {self.h}" role="img" aria-labelledby="{self.name}-t {self.name}-d" '
            f'xmlns="http://www.w3.org/2000/svg"><title id="{self.name}-t">{escape(self.title)}</title><desc id="{self.name}-d">'
            f"{escape(self.desc)}</desc>{MARKER.format(id=self.name + '-a')}{''.join(self.parts)}</svg>"
            f"<figcaption>{escape(self.title)}</figcaption></figure>"
        )


def seq_lifecycle() -> Markup:
    s = Seq("seqlife", "From a requirement to an approved change",
            "Sequence: the user picks or writes a spec, opslens validates and previews it read-only, the user approves the hash, Flowpipe runs it "
            "and pauses for approval before any change.",
            [("You", ""), ("opslens", "CLI / web app"), ("Steampipe", "read-only"), ("Flowpipe", "server"), ("Your services", "Jira, Teams, AWS")], 15)
    s.msg(0, 1, "pick a template or write a spec")
    s.msg(1, 1, "validate, SQL guard, render mod")
    s.msg(1, 0, "spec hash + plain-English explanation", dash=True)
    s.msg(0, 1, "preview")
    s.msg(1, 2, "SELECT ... (read-only)")
    s.msg(2, 1, "rows", dash=True)
    s.msg(1, 0, "exact arguments per action; nothing sent", dash=True)
    s.gate("You review, then approve the spec hash")
    s.msg(0, 1, "deploy --approve <hash>")
    s.msg(1, 3, "start server for this mod")
    s.msg(0, 1, "run (or schedule fires)")
    s.msg(3, 2, "find the rows")
    s.msg(3, 4, "notify actions: tickets, messages")
    s.gate("Change actions pause: a person approves in browser, app or terminal")
    s.msg(3, 4, "approved changes run")
    return s.render()


def seq_ai() -> Markup:
    s = Seq("seqai", "Drafting with AI: the model never writes pipeline code",
            "Sequence: opslens sends only the requirement and catalog excerpts to the model, validates the returned spec, feeds errors back, "
            "and shows the user a validated spec.",
            [("You", ""), ("opslens", "planner"), ("AI model", "optional"), ("Validator", "+ renderer")], 10, width=860)
    s.msg(0, 1, "generate \"your sentence\"")
    s.msg(1, 1, "scrub emails, ARNs, account ids")
    s.msg(1, 2, "sentence + catalog excerpt")
    s.msg(2, 1, "one YAML spec", dash=True)
    s.msg(1, 3, "validate")
    s.msg(3, 1, "errors (if any): fix these", dash=True)
    s.msg(1, 2, "retry, at most 3 attempts")
    s.msg(1, 3, "valid spec -> render mod")
    s.msg(1, 0, "validated spec to read, preview, approve", dash=True)
    return s.render()


def seq_team() -> Markup:
    s = Seq("seqteam", "Team mode: sign-in and a request",
            "Sequence: the browser reaches opslens through an HTTPS proxy, signs in with the shared password to get a signed session cookie, "
            "and every later request carries it plus a per-session token.",
            [("Browser", ""), ("HTTPS proxy", "Caddy"), ("opslens", "team mode"), ("Flowpipe", "")], 9, width=860)
    s.msg(0, 1, "open the site (HTTPS)")
    s.msg(1, 2, "forward")
    s.msg(2, 0, "303 to the sign-in page", dash=True)
    s.msg(0, 2, "POST /api/login (password)")
    s.msg(2, 2, "check, rate limit, sign cookie")
    s.msg(2, 0, "HttpOnly session cookie", dash=True)
    s.msg(0, 2, "API call + cookie + session token")
    s.msg(2, 3, "deploy, run, approve")
    s.msg(2, 2, "audit entry names the user")
    return s.render()


def all_diagrams() -> dict[str, Markup]:
    return {"c4_context": c4_context(), "c4_containers": c4_containers(), "c4_components": c4_components(),
            "seq_lifecycle": seq_lifecycle(), "seq_ai": seq_ai(), "seq_team": seq_team()}
