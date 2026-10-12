#!/usr/bin/env python3
"""Render the neofetch-style "whoami" card from profile.json as a terminal
window SVG that sits beside the ASCII portrait.

Both panels are 840 x 880 so they line up at equal widths in the README. The
card is shown at half size there, so every font here is at least 32px, which
lands at 16px on screen. Lines type in one after another (SMIL clip wipes,
which github.com runs inside <img> SVGs) and a cursor blinks at the end.

    python scripts/render_whoami_card.py [profile.json] [whoami-card.svg]
    STATIC=1 python scripts/render_whoami_card.py       # frozen frame for previews
"""
import html
import json
import os
import sys
import textwrap

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "profile.json")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "whoami-card.svg")
STATIC = bool(os.environ.get("STATIC"))

W, H = 840, 880
PAD = 24
TITLEBAR_H = 30
FONT = 32                 # 16px when the card is shown at 420px wide
LINE_H = 40
CHAR_W = FONT * 0.6       # monospace advance width
MAX_CHARS = int((W - PAD * 2) // CHAR_W)   # 41 at these sizes
LABEL_W = 8               # label column, in characters

BG, BG2, FRAME = "#0d1117", "#111722", "#30363d"
MUTED, INK = "#7d8590", "#e6edf3"
BLUE, ORANGE, GREEN = "#79c0ff", "#ffa657", "#7ee787"

LINE_SECONDS = 0.32       # one line's wipe
STAGGER = 0.17            # gap between line starts

with open(SRC, encoding="utf-8") as f:
    p = json.load(f)

prompt = p.get("prompt", "me@github")


def esc(s):
    return html.escape(s, quote=False)


# ---- build the lines: each line is a list of (text, colour, bold) segments
lines = []


def add_row(label, value, label_color=ORANGE):
    """Label in a fixed column, value wrapped onto continuation lines."""
    wrapped = textwrap.wrap(value, width=MAX_CHARS - LABEL_W) or [""]
    lines.append([(label.ljust(LABEL_W), label_color, False), (wrapped[0], INK, False)])
    for cont in wrapped[1:]:
        lines.append([(" " * LABEL_W, INK, False), (cont, INK, False)])


def add_bullet(text):
    wrapped = textwrap.wrap(text, width=MAX_CHARS - 2)
    lines.append([("• ", GREEN, False), (wrapped[0], INK, False)])
    for cont in wrapped[1:]:
        lines.append([("  ", INK, False), (cont, INK, False)])


lines.append([(prompt, BLUE, True)])
lines.append([("─" * min(len(prompt), MAX_CHARS), MUTED, False)])
for label, value in p["about"]:
    add_row(label, value)
for section in p.get("sections", []):
    lines.append([])
    lines.append([("> " + section["title"], BLUE, True)])
    for label, value in section.get("rows", []):
        add_row(label, value)
    for text in section.get("bullets", []):
        add_bullet(text)

content_h = H - TITLEBAR_H - PAD * 2
capacity = int(content_h // LINE_H)
if len(lines) > capacity:
    sys.exit(f"whoami card: {len(lines)} lines but only {capacity} fit; "
             f"trim profile.json by {len(lines) - capacity} line(s)")

# ---- svg
parts = [
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" '
    f"font-family=\"ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace\">",
    f'<defs><linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">'
    f'<stop offset="0" stop-color="{BG2}"/><stop offset="1" stop-color="{BG}"/></linearGradient></defs>',
    f'<rect width="{W}" height="{H}" rx="12" fill="url(#bg)"/>',
    f'<rect x="0.5" y="0.5" width="{W - 1}" height="{H - 1}" rx="12" fill="none" stroke="{FRAME}"/>',
    f'<line x1="0" y1="{TITLEBAR_H}" x2="{W}" y2="{TITLEBAR_H}" stroke="{FRAME}"/>',
]
for i, dot in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")):
    parts.append(f'<circle cx="{20 + i * 16}" cy="{TITLEBAR_H / 2}" r="5" fill="{dot}"/>')
parts.append(f'<text x="{W / 2}" y="{TITLEBAR_H / 2 + 4}" fill="{MUTED}" font-size="12" '
             f'text-anchor="middle">{esc(prompt)}: ~$ ./whoami.sh</text>')

top = TITLEBAR_H + PAD + (content_h - len(lines) * LINE_H) / 2  # centre the block vertically
last_end = 0.0
for i, segments in enumerate(lines):
    y = top + i * LINE_H
    baseline = y + LINE_H * 0.72
    if not segments:
        continue
    spans = ""
    for text, color, bold in segments:
        weight = ' font-weight="700"' if bold else ""
        spans += f'<tspan fill="{color}"{weight}>{esc(text)}</tspan>'
    text_el = f'<text xml:space="preserve" x="{PAD}" y="{baseline:.1f}" font-size="{FONT}">{spans}</text>'
    if STATIC:
        parts.append(text_el)
        continue
    begin = i * STAGGER
    last_end = begin + LINE_SECONDS
    parts.append(
        f'<clipPath id="l{i}"><rect x="{PAD}" y="{y:.1f}" width="0" height="{LINE_H}">'
        f'<animate attributeName="width" from="0" to="{W - PAD * 2}" begin="{begin:.2f}s" '
        f'dur="{LINE_SECONDS}s" fill="freeze"/></rect></clipPath>'
        f'<g clip-path="url(#l{i})">{text_el}</g>'
    )

# blinking block cursor on the line after the last one
cursor_y = top + len(lines) * LINE_H + LINE_H * 0.72 - FONT * 0.8
if STATIC:
    anim = ""
else:
    anim = (f'<set attributeName="opacity" to="1" begin="{last_end:.2f}s"/>'
            f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.51;1" dur="1s" '
            f'begin="{last_end:.2f}s" repeatCount="indefinite"/>')
parts.append(
    f'<rect x="{PAD}" y="{cursor_y:.1f}" width="{CHAR_W:.1f}" height="{FONT * 0.95:.1f}" fill="{INK}" '
    f'opacity="{1 if STATIC else 0}">{anim}</rect>'
)
parts.append("</svg>")

svg = "".join(parts)
with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    f.write(svg)
print(f"wrote {OUT}: {len(lines)}/{capacity} lines, {len(svg) // 1024} KB")
