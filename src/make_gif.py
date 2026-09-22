"""Render the replay as an animated GIF for the README.

Drawn straight from web/data.js rather than screen-captured, so the frames
cannot drift from the numbers the page and the arms report.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
W, H = 1000, 560
BG, INK, DIM = (250, 249, 245), (24, 24, 27), (120, 120, 128)
ACC, NEG, POS = (37, 99, 235), (200, 60, 60), (22, 140, 90)
GRID = (228, 226, 220)


def font(sz, bold=False):
    for p in ("/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else
              "/System/Library/Fonts/Supplemental/Arial.ttf",
              "/System/Library/Fonts/Helvetica.ttc"):
        try:
            return ImageFont.truetype(p, sz)
        except OSError:
            continue
    return ImageFont.load_default()


F = {k: font(*v) for k, v in {
    "h": (30, True), "n": (25, True), "l": (13, False), "s": (12, False),
    "m": (14, False), "b": (14, True), "t": (12, False)}.items()}


def money(v):
    return f"${v:,.0f}"


def render(d, i, path):
    eq, spx, dates = d["equity"], d["spx"], d["dates"]
    im = Image.new("RGB", (W, H), BG)
    g = ImageDraw.Draw(im)

    # ---- header ---------------------------------------------------------
    g.text((34, 26), "Jev Can Trade Stocks", font=F["h"], fill=INK)
    g.text((34, 64), f"{dates[i]}   ·   day {i+1} of {len(dates)}"
                     f"   ·   market {d['regime'][i]}", font=F["m"], fill=DIM)
    for n, (lab, val, col) in enumerate((
            ("PORTFOLIO", money(eq[i]), ACC),
            ("S&P 500", money(spx[i]), DIM),
            ("vs INDEX", f"{(eq[i]/spx[i]-1)*100:+.1f}%",
             POS if eq[i] >= spx[i] else NEG))):
        x = 610 + n * 130
        g.text((x, 30), lab, font=F["s"], fill=DIM)
        g.text((x, 48), val, font=F["n"], fill=col)

    # ---- equity curve ---------------------------------------------------
    L, T, R, B = 116, 112, W - 34, 356
    lo = min(min(eq[:i+1]), min(spx[:i+1])) * 0.97
    hi = max(max(eq[:i+1]), max(spx[:i+1])) * 1.03
    hi = max(hi, lo * 1.05)
    sx = lambda k: L + (R - L) * k / max(len(dates) - 1, 1)
    sy = lambda v: B - (B - T) * (v - lo) / (hi - lo)
    for frac in (0, .25, .5, .75, 1):
        y = T + (B - T) * frac
        g.line([(L, y), (R, y)], fill=GRID)
        lab = money(hi - (hi - lo) * frac)
        g.text((L - 10 - g.textlength(lab, font=F["s"]), y - 7), lab,
               font=F["s"], fill=DIM)
    for series, col, wid in ((spx, DIM, 2), (eq, ACC, 3)):
        pts = [(sx(k), sy(series[k])) for k in range(i + 1)]
        if len(pts) > 1:
            g.line(pts, fill=col, width=wid, joint="curve")
    if i:
        g.ellipse([sx(i) - 5, sy(eq[i]) - 5, sx(i) + 5, sy(eq[i]) + 5],
                  fill=ACC)
    g.line([(L, B), (R, B)], fill=(200, 198, 192))
    g.text((L, B + 10), "— portfolio (Jev deciding)", font=F["s"], fill=ACC)
    g.text((L + 190, B + 10), "— S&P 500", font=F["s"], fill=DIM)

    # ---- holdings -------------------------------------------------------
    y = 432
    g.text((34, y - 22), "HOLDINGS", font=F["s"], fill=DIM)
    pos = d["positions"][i][:5]
    if not pos:
        g.text((34, y + 4), "all cash", font=F["m"], fill=DIM)
    for n, p in enumerate(pos):
        x = 34 + n * 132
        col = POS if p["pct"] >= 0 else NEG
        g.text((x, y), p["t"], font=F["b"], fill=INK)
        g.text((x, y + 19), f"{p['pct']:+.1f}%", font=F["m"], fill=col)
        g.text((x, y + 38), money(p["val"]), font=F["s"], fill=DIM)

    # ---- today's tape ---------------------------------------------------
    g.text((700, y - 22), "TODAY", font=F["s"], fill=DIM)
    tr = d["trades"][i][:4]
    if not tr:
        g.text((700, y), "—", font=F["m"], fill=DIM)
    for n, t in enumerate(tr):
        col = POS if t["side"] == "BUY" else NEG
        g.text((700, y + n * 19), f"{t['side']:<4} {t['ticker']}",
               font=F["b"], fill=col)
        extra = "" if t["side"] == "BUY" else f"  {t['pct']:+.1f}%"
        g.text((790, y + n * 19), f"{t['reason'][:22]}{extra}",
               font=F["t"], fill=DIM)

    g.line([(34, H - 34), (W - 34, H - 34)], fill=GRID)
    g.text((34, H - 26), "2022-01-03 → 2026-09-18  ·  $100,000  ·  long only  "
                         "·  one draw; see the jackknife in the README",
           font=F["s"], fill=DIM)
    im.save(path)


def main():
    s = (ROOT / "web" / "data.js").read_text()
    d = json.loads(s[s.index("{"):s.rindex("}") + 1])
    n = len(d["dates"])
    step = max(1, n // 200)                  # ~200 frames
    out = ROOT / "docs" / "replay_frames"
    out.mkdir(parents=True, exist_ok=True)
    for f in out.glob("*.png"):
        f.unlink()
    idx = list(range(0, n, step)) + [n - 1] * 12      # hold on the last frame
    for k, i in enumerate(idx):
        render(d, i, out / f"f{k:04d}.png")
        if k % 40 == 0:
            print(f"  {k}/{len(idx)}", flush=True)
    gif = ROOT / "docs" / "replay.gif"
    subprocess.run([
        "ffmpeg", "-y", "-loglevel", "error", "-framerate", "18",
        "-i", str(out / "f%04d.png"),
        "-vf", "scale=760:-1:flags=lanczos,split[a][b];"
               "[a]palettegen=max_colors=64[p];[b][p]paletteuse=dither=bayer",
        str(gif)], check=True)
    print(f"wrote {gif}  ({gif.stat().st_size/1e6:.1f} MB, {len(idx)} frames)")


if __name__ == "__main__":
    main()
