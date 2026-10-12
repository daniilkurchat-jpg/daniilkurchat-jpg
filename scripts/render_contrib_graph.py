#!/usr/bin/env python3
"""Render data/contributions.json as an animated contribution graph SVG.

Cells use GitHub's own green scale and pop in week by week, left to right.
github.com shows README SVGs through <img>, where CSS animations run but
JavaScript never does, so the animation is pure CSS keyframes.

    python scripts/render_contrib_graph.py [data/contributions.json] [contrib-graph.svg]
"""
import datetime as dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "data", "contributions.json")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "contrib-graph.svg")

CELL, GAP, RADIUS = 13, 3, 2.5
LEFT, TOP = 34, 24
STEP = CELL + GAP
LEVELS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
MUTED = "#7d8590"
INK = "#e6edf3"
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

REVEAL_SECONDS = 3.6   # time until the last cell has appeared
POP_SECONDS = 0.55     # one cell's pop animation

with open(SRC, encoding="utf-8") as f:
    data = json.load(f)
days = data["days"]
total = data["total_contributions"]

first = dt.date.fromisoformat(days[0]["date"])
last = dt.date.fromisoformat(days[-1]["date"])
first_sunday = first - dt.timedelta(days=(first.weekday() + 1) % 7)  # GitHub weeks start on Sunday
weeks = (last - first_sunday).days // 7 + 1

width = LEFT + weeks * STEP + 6
height = TOP + 7 * STEP + 22
max_order = (weeks - 1) + 6 * 0.55

# month labels: one per month change, dropping a first label that would collide
labels = []
prev_month = None
for wk in range(weeks):
    sunday = first_sunday + dt.timedelta(weeks=wk)
    if sunday < first:
        continue
    if sunday.month != prev_month:
        if labels and wk - labels[-1][0] < 3:
            labels.pop()
        labels.append((wk, MONTHS[sunday.month - 1]))
        prev_month = sunday.month
label_svg = "".join(
    f'<text class="lbl" x="{LEFT + wk * STEP}" y="{TOP - 8}">{name}</text>' for wk, name in labels
)
label_svg += "".join(
    f'<text class="lbl" x="2" y="{TOP + row * STEP + CELL - 2}">{name}</text>'
    for name, row in (("Mon", 1), ("Wed", 3), ("Fri", 5))
)

cells = []
for d in days:
    date = dt.date.fromisoformat(d["date"])
    wk = (date - first_sunday).days // 7
    row = (date.weekday() + 1) % 7
    x = LEFT + wk * STEP
    y = TOP + row * STEP
    delay = (wk + row * 0.55) / max_order * REVEAL_SECONDS
    level = max(0, min(4, d["level"]))
    cls = "c lit" if level else "c"
    cells.append(
        f'<rect class="{cls}" x="{x}" y="{y}" width="{CELL}" height="{CELL}" rx="{RADIUS}" '
        f'fill="{LEVELS[level]}" style="animation-delay:{delay:.3f}s"><title>{d["count"]} on {d["date"]}</title></rect>'
    )

svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" font-family="-apple-system,'Segoe UI',Helvetica,Arial,sans-serif">
<style>
  .lbl {{ fill:{MUTED}; font-size:13px; font-weight:600; }}
  .total {{ fill:{INK}; font-size:15px; font-weight:700; }}
  .c {{ transform-box:fill-box; transform-origin:center; opacity:0; animation:pop {POP_SECONDS}s ease-out both; }}
  .lit {{ animation:pop {POP_SECONDS}s ease-out both, glow {POP_SECONDS + 0.15:.2f}s ease-out both; }}
  @keyframes pop {{ 0% {{ opacity:0; transform:scale(.2); }} 60% {{ opacity:1; transform:scale(1.1); }} 100% {{ opacity:1; transform:scale(1); }} }}
  @keyframes glow {{ 0%, 45% {{ filter:brightness(2.4); }} 100% {{ filter:brightness(1); }} }}
  @media (prefers-reduced-motion: reduce) {{ .c {{ opacity:1 !important; animation:none !important; }} }}
</style>
{label_svg}
{''.join(cells)}
<text class="total" x="{LEFT}" y="{height - 6}">{total:,} contributions in the last year</text>
</svg>
"""
with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    f.write(svg)
print(f"wrote {OUT}: {len(days)} days over {weeks} weeks, {total:,} contributions, {len(svg) // 1024} KB")
