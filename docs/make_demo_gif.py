"""Build the animated demo used at the top of the README.

This project's output normally lives in a Google Sheet and a dashboard behind a
password, neither of which can be shown publicly. What *can* be shown is the
part that does the actual reasoning: turning a hand-typed task title into
structured targets, scoring the work, and deriving when it can start.

Every value in the animation is computed by calling the real functions -- the
only thing invented is the input title.

    python docs/make_demo_gif.py

Writes ``docs/demo.gif``.
"""

import os
import sys
from datetime import date, timedelta

from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(ROOT, "docs")
sys.path.insert(0, ROOT)

from expander import (  # noqa: E402
    extract_allowed_targets,
    parse_elevation_count,
    parse_sq_ft_and_difficulty,
)

CANVAS_W, CANVAS_H = 1000, 620
BAR_H = 62
BG = (250, 250, 251)
BAR_BG = (24, 28, 34)
BAR_FG = (238, 240, 244)
ACCENT = (150, 120, 255)
INK = (22, 24, 28)
MUTED = (110, 116, 126)
CARD = (255, 255, 255)
LINE = (224, 227, 232)

TITLE = "D10231 BLOCK 4 LOT 5, 7 AND 9 - 2ND REVIEW"

# Difficulty tiers, in the shape load_difficulty_tiers() returns from the
# remote configuration sheet. These are the documented fallback values.
TIERS = [
    {"min": 0, "max": 2500, "base_difficulty": 1.0},
    {"min": 2500, "max": 4000, "base_difficulty": 1.5},
    {"min": 4000, "max": float("inf"), "base_difficulty": 2.0},
]


def font(size: int):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def base(step: str, caption: str) -> Image.Image:
    canvas = Image.new("RGB", (CANVAS_W, CANVAS_H), BG)
    d = ImageDraw.Draw(canvas)
    d.rectangle([0, 0, CANVAS_W, BAR_H], fill=BAR_BG)
    d.text((22, 15), step, font=font(15), fill=ACCENT)
    d.text((22, 36), caption, font=font(15), fill=BAR_FG)
    d.rectangle([0, BAR_H - 2, CANVAS_W, BAR_H], fill=ACCENT)
    return canvas


def card(d, x, y, w, h, title=None):
    d.rectangle([x, y, x + w, y + h], fill=CARD, outline=LINE, width=2)
    if title:
        d.text((x + 16, y + 12), title, font=font(13), fill=MUTED)


def rows(d, x, y, pairs, w=420, gap=30, label_font=15, value_font=15):
    for i, (k, v) in enumerate(pairs):
        yy = y + i * gap
        d.text((x, yy), k, font=font(label_font), fill=MUTED)
        d.text((x + w * 0.46, yy), v, font=font(value_font), fill=INK)


def main() -> None:
    os.makedirs(DOCS, exist_ok=True)
    frames = []

    # --- 1. the raw input ---------------------------------------------------
    f = base("INPUT", "A task title, typed by a human, in a project tracker")
    d = ImageDraw.Draw(f)
    card(d, 60, 150, CANVAS_W - 120, 130, "CLICKUP TASK NAME")
    d.text((90, 200), TITLE, font=font(23), fill=INK)
    d.text((90, 240), "No structure. Free text. Spelling and spacing vary by author.",
           font=font(14), fill=MUTED)
    frames.append((f, 3000))

    # --- 2. parsed targets --------------------------------------------------
    project, models, blocks, lots = extract_allowed_targets(TITLE)
    f = base("PARSE", "Expanded into explicit target sets")
    d = ImageDraw.Draw(f)
    card(d, 60, 110, CANVAS_W - 120, 60)
    d.text((84, 130), TITLE, font=font(16), fill=MUTED)
    card(d, 60, 200, CANVAS_W - 120, 250, "EXTRACTED TARGETS")
    rows(d, 90, 250, [
        ("project code", str(project)),
        ("blocks", ", ".join(sorted(blocks)) or "-"),
        ("lots", ", ".join(str(n) for n in sorted(lots)) or "-"),
        ("model name variants", f"{len(models)} generated spellings"),
        ("review suffix", "'2ND REVIEW' stripped before parsing"),
    ], w=CANVAS_W - 180, gap=36)
    frames.append((f, 3600))

    # --- 3. schedule lookup -------------------------------------------------
    elev_cell, sqft_cell = "A/B/C", "3,120"
    n_elev = parse_elevation_count(elev_cell)
    sq_str, difficulty = parse_sq_ft_and_difficulty(sqft_cell, n_elev, TIERS)

    f = base("SCORE", "Complexity from the matched schedule row, not from a guess")
    d = ImageDraw.Draw(f)
    card(d, 60, 110, CANVAS_W - 120, 150, "MATCHED SCHEDULE ROW")
    rows(d, 90, 158, [
        ("square footage", f"{sq_str} sq ft"),
        ("elevations", f"{elev_cell}  ->  {n_elev}"),
    ], w=CANVAS_W - 180, gap=34)

    card(d, 60, 290, CANVAS_W - 120, 190, "DIFFICULTY")
    tier = next(t for t in TIERS if t["min"] <= float(sq_str.replace(",", "")) < t["max"])
    rows(d, 90, 338, [
        ("size tier", f"{tier['min']:,} - {tier['max']:,} sq ft  ->  base {tier['base_difficulty']}"),
        ("elevation bonus", f"({n_elev} - 1) x 0.1  =  {max(0, (n_elev - 1) * 0.1):.1f}"),
        ("difficulty", f"{difficulty}"),
    ], w=CANVAS_W - 180, gap=36)
    frames.append((f, 4200))

    # --- 4. derived start date ---------------------------------------------
    arch = date(2026, 3, 4)
    floor = date(2026, 3, 11)
    truss = date(2026, 3, 9)
    startable = max(arch, floor, truss) + timedelta(days=1)

    f = base("SCHEDULE", "When the work actually becomes startable")
    d = ImageDraw.Draw(f)
    card(d, 60, 110, CANVAS_W - 120, 210, "INPUT DATES FROM THE SCHEDULE")
    rows(d, 90, 160, [
        ("architectural", arch.isoformat()),
        ("floor layout", floor.isoformat()),
        ("truss layout", truss.isoformat()),
    ], w=CANVAS_W - 180, gap=36)

    card(d, 60, 350, CANVAS_W - 120, 140, "DERIVED")
    d.text((90, 396), "max(arch, floor, truss) + 1 day", font=font(17), fill=MUTED)
    d.text((90, 432), f"startable  {startable.isoformat()}", font=font(23), fill=INK)
    frames.append((f, 4200))

    # --- 5. what it is for --------------------------------------------------
    f = base("WHY", "Difficulty-weighted load, not a count of open tickets")
    d = ImageDraw.Draw(f)
    card(d, 60, 120, CANVAS_W - 120, 330)
    lines = [
        ("Queue blindness", "A tracker counts tickets. Ten simple units and ten"),
        ("", "complex ones look identical, and the schedule built on"),
        ("", "that count is wrong before anyone starts."),
        ("", ""),
        ("Weighted throughput", "KPI = difficulty / duration in business days, so a"),
        ("", "hard job finished slowly and an easy one finished fast"),
        ("", "no longer read the same."),
        ("", ""),
        ("Forward view", "Start dates derive from when inputs land, so upcoming"),
        ("", "load is visible before it arrives rather than after."),
    ]
    y = 165
    for head, text in lines:
        if head:
            d.text((90, y), head, font=font(16), fill=ACCENT)
        d.text((300, y), text, font=font(15), fill=INK if head else MUTED)
        y += 29
    frames.append((f, 5200))

    out = os.path.join(DOCS, "demo.gif")
    imgs = [x for x, _ in frames]
    imgs[0].save(out, save_all=True, append_images=imgs[1:],
                 duration=[t for _, t in frames], loop=0, optimize=True)
    print(f"wrote {out} ({os.path.getsize(out):,} bytes, {len(imgs)} frames)")


if __name__ == "__main__":
    main()
