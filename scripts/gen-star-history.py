#!/usr/bin/env python3
"""Regenerate assets/star-history.svg from live GitHub stargazer data.

Why static: the free api.star-history.com endpoint shares a GitHub token pool
and is frequently rate-limited (HTTP 503), so the live embed often fails to
load. This bakes a self-contained SVG instead — always renders, no external
dependency at view time. Re-run it whenever the star count has grown enough
to be worth refreshing.

Usage:
    python3 scripts/gen-star-history.py
    # then: git add assets/star-history.svg && git commit && git push

Requirements: `gh` CLI authenticated (uses your token to avoid the 60/hr
anonymous rate limit). If you sit behind a proxy, export HTTPS_PROXY first.
"""
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

REPO = "Minara-AI/skills"
OUT = os.path.join(os.path.dirname(__file__), "..", "assets", "star-history.svg")

GREEN = "#1AB173"          # Minara brand green
AXIS = "#8b949e"           # neutral gray — readable on GitHub light & dark
GRID = "#8b949e"


def fetch_starred_at():
    """Return sorted list of starred_at datetimes via the authenticated gh CLI."""
    try:
        raw = subprocess.check_output(
            ["gh", "api", "-H", "Accept: application/vnd.github.star+json",
             f"/repos/{REPO}/stargazers?per_page=100", "--paginate",
             "--jq", ".[].starred_at"],
            text=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        sys.exit(f"failed to fetch stargazers via gh: {e}\n"
                 "Ensure `gh auth status` is logged in (and HTTPS_PROXY is set if needed).")
    ts = [datetime.strptime(l.strip(), "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
          for l in raw.splitlines() if l.strip()]
    ts.sort()
    return ts


def nice_ticks(maxv, n=5):
    step = maxv / n
    mag = 10 ** (len(str(int(step))) - 1)
    step = round(step / mag) * mag or mag
    ticks, v = [], 0
    while v <= maxv:
        ticks.append(v)
        v += step
    return ticks


def build_svg(ts):
    now = datetime.now(timezone.utc)
    pts = [(t.timestamp(), i + 1) for i, t in enumerate(ts)]
    pts.append((now.timestamp(), pts[-1][1]))  # carry flat to right edge

    x0, x1 = pts[0][0], pts[-1][0]
    ymax = pts[-1][1]

    W, H = 840, 420
    ml, mr, mt, mb = 64, 24, 56, 52
    pw, ph = W - ml - mr, H - mt - mb

    def sx(x): return ml + (x - x0) / (x1 - x0) * pw
    def sy(y): return mt + ph - (y / ymax) * ph

    poly = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in pts)
    area = (f"M{sx(pts[0][0]):.1f},{sy(0):.1f} "
            + " ".join(f"L{sx(x):.1f},{sy(y):.1f}" for x, y in pts)
            + f" L{sx(pts[-1][0]):.1f},{sy(0):.1f} Z")

    s = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
         f'viewBox="0 0 {W} {H}" font-family="-apple-system,BlinkMacSystemFont,'
         f'Segoe UI,Helvetica,Arial,sans-serif">',
         f'<defs><linearGradient id="g" x1="0" y1="0" x2="0" y2="1">'
         f'<stop offset="0%" stop-color="{GREEN}" stop-opacity="0.28"/>'
         f'<stop offset="100%" stop-color="{GREEN}" stop-opacity="0.02"/></linearGradient></defs>',
         f'<text x="{ml}" y="30" font-size="16" font-weight="600" fill="{GREEN}">'
         f'{REPO} — Star History</text>']

    for v in nice_ticks(ymax):
        y = sy(v)
        s.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{W-mr}" y2="{y:.1f}" '
                 f'stroke="{GRID}" stroke-opacity="0.18" stroke-width="1"/>')
        s.append(f'<text x="{ml-10}" y="{y+4:.1f}" font-size="12" fill="{AXIS}" '
                 f'text-anchor="end">{int(v)}</text>')

    seen, months = set(), []
    for x, _ in pts:
        d = datetime.fromtimestamp(x, tz=timezone.utc)
        if (d.year, d.month) not in seen:
            seen.add((d.year, d.month))
            months.append((datetime(d.year, d.month, 1, tzinfo=timezone.utc).timestamp(),
                           d.strftime("%b %Y")))
    for xv, lab in months:
        x = sx(max(xv, x0))
        s.append(f'<text x="{x:.1f}" y="{H-mb+22}" font-size="12" fill="{AXIS}" '
                 f'text-anchor="middle">{lab}</text>')

    s.append(f'<path d="{area}" fill="url(#g)"/>')
    s.append(f'<polyline points="{poly}" fill="none" stroke="{GREEN}" '
             f'stroke-width="2.5" stroke-linejoin="round" stroke-linecap="round"/>')
    ex, ey = sx(pts[-1][0]), sy(pts[-1][1])
    s.append(f'<circle cx="{ex:.1f}" cy="{ey:.1f}" r="4" fill="{GREEN}"/>')
    s.append(f'<text x="{ex-8:.1f}" y="{ey-10:.1f}" font-size="13" font-weight="600" '
             f'fill="{GREEN}" text-anchor="end">{ymax} ★</text>')
    s.append(f'<line x1="{ml}" y1="{mt}" x2="{ml}" y2="{H-mb}" stroke="{AXIS}" '
             f'stroke-opacity="0.4" stroke-width="1"/>')
    s.append(f'<line x1="{ml}" y1="{H-mb}" x2="{W-mr}" y2="{H-mb}" stroke="{AXIS}" '
             f'stroke-opacity="0.4" stroke-width="1"/>')
    s.append('</svg>')
    return "\n".join(s), ymax


def main():
    ts = fetch_starred_at()
    if not ts:
        sys.exit("no stargazers returned")
    svg, ymax = build_svg(ts)
    with open(OUT, "w") as f:
        f.write(svg)
    print(f"wrote {os.path.normpath(OUT)}  ({ymax} stars, "
          f"{ts[0].date()} .. {datetime.now(timezone.utc).date()})")


if __name__ == "__main__":
    main()
