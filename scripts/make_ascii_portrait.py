#!/usr/bin/env python3
"""Turn a prepared portrait (grayscale, subject on white, see prep_photo.py)
into a monochrome ASCII-art SVG that prints itself row by row like a terminal,
then holds. One ink colour on a dark window keeps it clean and legible.

github.com shows README SVGs through <img>: SMIL animations run there,
JavaScript does not, so the reveal is a per-row clip wipe with a cursor riding
the wipe edge.

    python scripts/make_ascii_portrait.py [source-prepped.png] [portrait-ascii.svg]
    COLS=200 python scripts/make_ascii_portrait.py      # more detail
    STATIC=1 python scripts/make_ascii_portrait.py      # frozen frame for previews
"""
import html
import json
import os
import sys

from PIL import Image, ImageEnhance, ImageFilter

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, ".."))
SRC = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ROOT, "source-prepped.png")
OUT = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, "portrait-ascii.svg")
STATIC = bool(os.environ.get("STATIC"))

with open(os.path.join(ROOT, "profile.json"), encoding="utf-8") as f:
    p = json.load(f)
prompt = p.get("prompt", "me@github")
name = p.get("name", "")
INK = p.get("portrait_color", "#a5d6ff")

COLS = int(os.environ.get("COLS", p.get("portrait_cols", 160)))
RAMP = os.environ.get("RAMP", " .:-=+*#%@")   # light (sparse) to dark (dense)
CONTRAST = float(os.environ.get("CONTRAST", 1.1))
GAMMA = float(os.environ.get("GAMMA", 1.0))   # > 1 pushes skin into sparser characters
WHITE_FLOOR = float(os.environ.get("WHITE_FLOOR", 0.9))  # brighter than this prints as blank
EDGE = float(os.environ.get("EDGE", 0.45))   # how much detected edges darken the result

# canvas: same 840 x 880 as the whoami card so the two line up in the README
W, H = 840, 880
PAD = 20
TITLEBAR_H = 30
STATUS_H = 30
ART_W = W - PAD * 2
CELL_W = ART_W / COLS
CELL_H = CELL_W * 15 / 8          # a monospace cell is about 8 wide by 15 tall
ROWS = int((H - TITLEBAR_H - STATUS_H - PAD) // CELL_H)
ART_H = ROWS * CELL_H
art_top = TITLEBAR_H + (H - TITLEBAR_H - STATUS_H - ART_H) / 2

BG, BG2, FRAME, MUTED = "#0d1117", "#111722", "#30363d", "#7d8590"
TOTAL_SECONDS = 5.8
ROW_SECONDS = TOTAL_SECONDS / ROWS

# ---- sample the image into a COLS x ROWS grid
im = Image.open(SRC).convert("L")
if im.width != im.height:  # centre-crop to square so nothing is squashed
    side = min(im.size)
    im = im.crop(((im.width - side) // 2, (im.height - side) // 2,
                  (im.width + side) // 2, (im.height + side) // 2))
im = ImageEnhance.Contrast(im).enhance(CONTRAST)
edges = im.filter(ImageFilter.FIND_EDGES).filter(ImageFilter.GaussianBlur(1.2))
small = im.resize((COLS, ROWS), Image.LANCZOS).load()
small_edges = edges.resize((COLS, ROWS), Image.LANCZOS).load()

rows_txt = []
for y in range(ROWS):
    chars = []
    for x in range(COLS):
        lum = pow(small[x, y] / 255.0, GAMMA)
        lum -= EDGE * (small_edges[x, y] / 255.0)
        lum = max(0.0, min(1.0, lum))
        if lum >= WHITE_FLOOR:
            chars.append(" ")
            continue
        idx = round((1.0 - lum) * (len(RAMP) - 1))
        chars.append(RAMP[max(0, min(len(RAMP) - 1, idx))])
    rows_txt.append("".join(chars))

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
    parts.append(f'<circle cx="{PAD + i * 16}" cy="{TITLEBAR_H / 2}" r="5" fill="{dot}"/>')
parts.append(f'<text x="{W / 2}" y="{TITLEBAR_H / 2 + 4}" fill="{MUTED}" font-size="12" '
             f'text-anchor="middle">{html.escape(prompt)}: ~$ ./portrait.sh</text>')

font_size = CELL_H * 0.86
for r, line in enumerate(rows_txt):
    row_y = art_top + r * CELL_H
    baseline = row_y + CELL_H * 0.74
    text = (f'<text xml:space="preserve" x="{PAD}" y="{baseline:.1f}" fill="{INK}" '
            f'font-size="{font_size:.2f}" textLength="{ART_W}" lengthAdjust="spacing">{html.escape(line)}</text>')
    if STATIC or not line.strip():
        parts.append(text)
        continue
    begin = r * ROW_SECONDS
    parts.append(
        f'<clipPath id="r{r}"><rect x="{PAD}" y="{row_y:.1f}" width="0" height="{CELL_H:.2f}">'
        f'<animate attributeName="width" from="0" to="{ART_W}" begin="{begin:.3f}s" dur="{ROW_SECONDS:.3f}s" fill="freeze"/>'
        f'</rect></clipPath><g clip-path="url(#r{r})">{text}</g>'
        f'<rect y="{row_y + 1:.1f}" width="{CELL_W:.2f}" height="{CELL_H - 2:.2f}" fill="{INK}" opacity="0">'
        f'<animate attributeName="x" from="{PAD}" to="{PAD + ART_W}" begin="{begin:.3f}s" dur="{ROW_SECONDS:.3f}s" fill="freeze"/>'
        f'<set attributeName="opacity" to="0.85" begin="{begin:.3f}s"/>'
        f'<set attributeName="opacity" to="0" begin="{begin + ROW_SECONDS:.3f}s"/></rect>'
    )

# status bar: prompt + name + blinking cursor
status_line_y = H - STATUS_H
status_y = status_line_y + 20
parts.append(f'<line x1="0" y1="{status_line_y}" x2="{W}" y2="{status_line_y}" stroke="{FRAME}"/>')
parts.append(f'<text x="{PAD}" y="{status_y}" fill="{MUTED}" font-size="13">'
             f'{html.escape(prompt)}:~$ whoami <tspan fill="{INK}">{html.escape(name)}</tspan></text>')
cursor_x = PAD + len(f"{prompt}:~$ whoami {name} ") * 13 * 0.6
parts.append(f'<rect x="{cursor_x:.1f}" y="{status_y - 12}" width="8" height="14" fill="{INK}">'
             f'<animate attributeName="opacity" values="1;1;0;0" keyTimes="0;0.5;0.51;1" dur="1s" repeatCount="indefinite"/></rect>')
parts.append("</svg>")

svg = "".join(parts)
with open(OUT, "w", encoding="utf-8", newline="\n") as f:
    f.write(svg)
inked = sum(1 for line in rows_txt for ch in line if ch != " ")
print(f"wrote {OUT}: {COLS} x {ROWS} cells, {inked} inked, {len(svg) // 1024} KB")
