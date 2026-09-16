"""Generate docs/system.svg — the three-plane system diagram.

Committed as a generator rather than a hand-edited SVG so every coordinate is computed from one
grid. Editing 400 lines of path data by hand is how a diagram acquires a misaligned label that
nobody notices for a year.

    python3 scripts/gen_system_svg.py

Palette and type follow the practice's 'Ledger' direction: bone ground, pine and amber accents,
hairline rules instead of filled cards. The amber is spent on exactly one thing — the model — because
that is the single claim the diagram makes.
"""
import pathlib

W, H = 1160, 960
SPINE = 120
X0, X1 = 170, 1110
COLW = 216
GAP = 25
COL = [X0 + i * (COLW + GAP) for i in range(4)]
COL[3] = X0 + 3 * (COLW + GAP)
LASTW = X1 - COL[3]

P = dict(
    ground="#F7F5EF", panel="#FFFFFF", ink="#16211C", muted="#6A716A",
    rule="#D6D0C0", hair="#E4DFD2", pine="#1F4D3D", pinewash="#EDF2EE",
    amber="#B4560F", amberwash="#FBF0E6", store="#EFECE2", storeline="#A8A294",
)
F = "system-ui,-apple-system,'Segoe UI',Roboto,Helvetica,Arial,sans-serif"
M = "ui-monospace,'SF Mono',Menlo,Consolas,monospace"

o = []
def add(s): o.append(s)

def esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def text(x, y, s, size=14, fill=P["ink"], weight="400", anchor="start",
         font=F, spacing="0", opacity="1"):
    add(f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" font-weight="{weight}" '
        f'fill="{fill}" text-anchor="{anchor}" letter-spacing="{spacing}" opacity="{opacity}">'
        f'{esc(s)}</text>')

def box(x, y, w, h, fill=P["panel"], stroke=P["rule"], sw=1, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="2" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="{sw}"{d}/>')

def node(x, y, w, h, title, lines, fill=P["panel"], stroke=P["rule"], sw=1,
         tcol=None, accent=None):
    box(x, y, w, h, fill, stroke, sw)
    if accent:                      # a 3px rule on the left edge, not a coloured card
        add(f'<rect x="{x}" y="{y}" width="3" height="{h}" fill="{accent}"/>')
    cy = y + 26 if lines else y + h / 2 + 5
    text(x + 16, cy, title, 14.5, tcol or P["ink"], "600")
    for i, ln in enumerate(lines):
        text(x + 16, cy + 19 + i * 15, ln, 11.5, P["muted"], "400", font=M)

def arrow(x1, y1, x2, y2, dash=None, col=None, head=True):
    col = col or P["ink"]
    d = f' stroke-dasharray="{dash}"' if dash else ""
    mk = ' marker-end="url(#a)"' if head else ""
    add(f'<path d="M {x1} {y1} L {x2} {y2}" fill="none" stroke="{col}" '
        f'stroke-width="1.3"{d}{mk}/>')

def elbow(x1, y1, xm, y2, x2, dash=None, col=None):
    col = col or P["ink"]
    d = f' stroke-dasharray="{dash}"' if dash else ""
    add(f'<path d="M {x1} {y1} H {xm} V {y2} H {x2}" fill="none" stroke="{col}" '
        f'stroke-width="1.3"{d} marker-end="url(#a)"/>')

def band(y, num, name, note):
    text(X0, y, f"{num}", 12, P["muted"], "600", font=M, spacing="0.08em")
    text(X0 + 26, y, name.upper(), 12, P["ink"], "700", spacing="0.14em")
    text(X0 + 26 + len(name) * 9.2 + 18, y, note, 12, P["muted"], "400")
    add(f'<line x1="{X0}" y1="{y + 12}" x2="{X1}" y2="{y + 12}" stroke="{P["ink"]}" stroke-width="1.5"/>')

add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" '
    f'role="img" aria-label="The harness in three planes: request, measurement, projection.">')
add(f'<defs><marker id="a" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" '
    f'orient="auto-start-reverse"><path d="M 0 1 L 9 5 L 0 9 z" fill="{P["ink"]}"/></marker></defs>')
add(f'<rect width="{W}" height="{H}" fill="{P["ground"]}"/>')

# ---- band 1 ------------------------------------------------------------------------------
band(86, "01", "Request", "· a model is inside this loop, and nowhere else")
box(X0, 118, COLW, 44, P["ground"], P["storeline"], 1, "3 3")
text(X0 + 16, 145, "question + gold", 13, P["muted"], "500")
arrow(X0 + COLW / 2, 162, X0 + COLW / 2, 194)

node(COL[0], 196, COLW, 82, "orchestrator", ["agent/loop.py"])
node(COL[1], 196, COLW, 82, "guardrails", ["action_space · before", "disclosure · after"])
node(COL[2], 196, COLW, 82, "tools", ["query_metric · run_sql", "answer|refuse|clarify"])
node(COL[3], 196, LASTW, 82, "semantic layer", ["governed metrics", "segments · metric tree"])
for i in range(3):
    arrow(COL[i] + COLW, 237, COL[i + 1] - 4, 237)

# the return leg of the loop, drawn rather than implied
add(f'<path d="M {COL[2] + 40} 278 V 302 H {COL[0] + 34} V 282" fill="none" stroke="{P["muted"]}" '
    f'stroke-width="1.1" stroke-dasharray="3 3" marker-end="url(#a)"/>')
text(COL[1] + 46, 298, "observe, loop", 11, P["muted"], "400", font=M)

node(COL[0], 320, COLW, 52, "model", ["provider API · tokens · cost"],
     P["amberwash"], P["amber"], 1.4, P["amber"], P["amber"])
node(COL[3], 320, LASTW, 52, "warehouse", ["DuckDB · dim_/fct_ views"], P["store"], P["storeline"])
add(f'<path d="M {COL[0] + COLW/2} 282 V 316" stroke="{P["amber"]}" stroke-width="1.3" '
    f'marker-end="url(#a)" marker-start="url(#a)"/>')
arrow(COL[3] + LASTW / 2, 282, COL[3] + LASTW / 2, 316)

# ---- band 2 ------------------------------------------------------------------------------
band(452, "02", "Measurement", "· deterministic. no model, no key, no network")
node(COL[0], 486, COLW, 82, "one recorder", ["evals/row.py"])
node(COL[1], 486, COLW, 82, "grader", ["evals/grade.py", "imports re. calls no model"])
node(COL[2], 486, COLW, 82, "statistics", ["bootstrap over questions", "stats · selective · utility"])
node(COL[3], 486, LASTW, 82, "report", ["evals/report.py"])
for i in range(3):
    arrow(COL[i] + COLW, 527, COL[i + 1] - 4, 527)

# the spine: request -> measurement
elbow(COL[0] - 4, 237, SPINE, 527, COL[0] - 4)
text(SPINE + 12, 392, "typed outcome", 11, P["muted"], "500", font=M)
text(SPINE + 12, 406, "+ telemetry", 11, P["muted"], "500", font=M)

# ---- the record --------------------------------------------------------------------------
box(X0, 620, X1 - X0, 58, P["store"], P["storeline"])
text(X0 + 18, 646, "system of record", 14.5, P["ink"], "600")
text(X0 + 18, 665, "raw.jsonl · summary.json · summary.md", 11.5, P["muted"], "400", font=M)
text(X1 - 18, 654, "every published number is recomputable from here", 12, P["muted"], "400", "end")
arrow(COL[3] + LASTW / 2, 572, COL[3] + LASTW / 2, 616)

# ---- band 3 ------------------------------------------------------------------------------
band(766, "03", "Projection", "· optional, one-way. absent by default")
node(COL[0], 800, COLW, 82, "publish", ["evals/publish.py", "render → emit"],
     P["panel"], P["storeline"], 1)
node(620, 800, 300, 82, "Langfuse", ["self-hosted · localhost:3100"],
     P["panel"], P["storeline"], 1)
arrow(COL[0] + COLW, 841, 616, 841)
text(501, 831, "OpenTelemetry spans · OTLP", 11, P["muted"], "500", "middle", font=M)
text(501, 860, "the SDK's wire format, not ours", 11, P["muted"], "400", "middle", font=M)

add(f'<path d="M {X0 - 4} 649 H {SPINE} V 841 H {X0 - 4}" fill="none" stroke="{P["muted"]}" '
    f'stroke-width="1.3" stroke-dasharray="4 3" marker-end="url(#a)"/>')
text(SPINE + 12, 710, "replay", 11, P["muted"], "500", font=M)
text(SPINE + 12, 725, "read-only", 11, P["muted"], "400", font=M)

add(f'<rect x="964" y="800" width="3" height="82" fill="{P["amber"]}"/>')
text(980, 820, "amber", 11.5, P["amber"], "600", font=M)
text(980, 837, "the only component that is not", 11.5, P["muted"], "400")
text(980, 853, "deterministic. everything below", 11.5, P["muted"], "400")
text(980, 869, "plane 01 replays without a key.", 11.5, P["muted"], "400")
text(X1, 922, "grade.py calls no model at any rung · the projection never writes back",
     12, P["muted"], "400", "end")

add("</svg>")
out = pathlib.Path(__file__).resolve().parent.parent / "docs" / "system.svg"
out.write_text("\n".join(o))
print(f"wrote {out} ({len(''.join(o))} bytes)")
