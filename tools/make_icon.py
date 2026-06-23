#!/usr/bin/env python3
"""Generate keepy.ico (and a keepy.png preview) - the app / .exe icon - from
Keepy's own pixel art: a front-facing Keepy with the football balanced on his
head, on a warm cream rounded-square backdrop.

This is a build-time / dev tool only - it is NOT needed to run Keepy. It needs
Pillow (the app itself stays standard-library only):

    pip install pillow
    python tools/make_icon.py

The art below mirrors the constants in keepy.py; keep them in sync if the
critter ever changes.
"""
import os
from PIL import Image, ImageDraw

# --- colours (mirror keepy.py) ---
BODY   = "#C16A4A"
LIMB   = "#A2543B"
EYE    = "#2b2b2b"
SMILE  = "#ffffff"
BG     = "#EFE6CE"          # warm cream backdrop
BORDER = "#9E4B33"          # ACCENT

BODY_GRID = [
    "..BBBBBBBBBBBB..",
    ".BBBBBBBBBBBBBB.",
    "BBBBBBBBBBBBBBBB",
    "BBBBBBBBBBBBBBBB",
    "BBBBBBBBBBBBBBBB",
    "BBBBBBBBBBBBBBBB",
    "BBBBBBBBBBBBBBBB",
    "BBBBBBBBBBBBBBBB",
    "BBBBBBBBBBBBBBBB",
    "BBBBBBBBBBBBBBBB",
]
LEG_COLS = [2, 5, 9, 12]
BALL_GRID = [
    ".ggggg.",
    "gWWWWWg",
    "gWDWDWg",
    "gWWDWWg",
    "gWDWDWg",
    "gWWWWWg",
    ".ggggg.",
]
BALL_PAL = {"g": "#b8b8b8", "W": "#ffffff", "D": "#262626"}


def build_cells():
    """(col, row, w, h, colour) art cells for the icon composition."""
    cells = []
    for col0 in (-4, 16):                       # resting arms (4 wide x 2 tall)
        cells.append((col0, 3, 4, 2, LIMB))
    for col in LEG_COLS:                         # little legs (2 wide x 2 tall)
        cells.append((col, 10, 2, 2, LIMB))
    for r, row in enumerate(BODY_GRID):          # the box body
        c = 0
        while c < len(row):
            if row[c] != "B":
                c += 1
                continue
            j = c
            while j < len(row) and row[j] == "B":
                j += 1
            cells.append((c, r, j - c, 1, BODY))
            c = j
    for ecol in (3, 11):                         # eyes (2x2)
        cells.append((ecol, 5, 2, 2, EYE))
    for sc, sr in [(6, 7), (9, 7), (7, 8), (8, 8)]:   # white smile, corners up
        cells.append((sc, sr, 1, 1, SMILE))
    bx0, by0 = 4.5, -7.0                          # football resting on his head
    for r, row in enumerate(BALL_GRID):
        for c, ch in enumerate(row):
            if ch in BALL_PAL:
                cells.append((bx0 + c, by0 + r, 1, 1, BALL_PAL[ch]))
    return cells


def render(size):
    cells = build_cells()
    xs0 = min(c[0] for c in cells)
    xs1 = max(c[0] + c[2] for c in cells)
    ys0 = min(c[1] for c in cells)
    ys1 = max(c[1] + c[3] for c in cells)
    artw, arth = xs1 - xs0, ys1 - ys0

    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    pad = size * 0.05
    d.rounded_rectangle([pad, pad, size - pad, size - pad], radius=size * 0.22,
                        fill=BG, outline=BORDER, width=max(1, int(size * 0.012)))

    margin = size * 0.15
    s = (size - 2 * margin) / max(artw, arth)
    ox = (size - artw * s) / 2 - xs0 * s
    oy = (size - arth * s) / 2 - ys0 * s
    for (col, row, w, h, color) in cells:
        x0, y0 = ox + col * s, oy + row * s
        d.rectangle([x0, y0, x0 + w * s, y0 + h * s], fill=color)
    return img


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    base = render(256)
    base.save(os.path.join(root, "keepy.ico"),
              sizes=[(256, 256), (128, 128), (64, 64), (48, 48), (32, 32), (16, 16)])
    base.save(os.path.join(root, "keepy.png"))   # preview
    print("wrote keepy.ico + keepy.png in", root)


if __name__ == "__main__":
    main()
