"""Render a track-mapper CSV as an SVG map, viewable in any browser.

Handles both CSV shapes this project produces:

  - Real firmware output (main.py's on-device track_log.csv):
    t_ms,x_mm,y_mm,theta_rad,lap -- already-fused position, one row per
    sample. Drawn as one polyline per lap value (lap 0 is the pre-tape
    rollout under a rolling start, DESIGN.md SS6; dashed since its origin
    is an arbitrary power-on position, not the tape).

  - Simulator output (sim/simulate_track_run.py's expected_track_run.csv):
    raw synthetic sensor columns plus gt_x_mm/gt_y_mm (true path, from the
    source SVG track) and recon_x_mm/recon_y_mm (what main.py's own fusion
    math reconstructs from the synthetic sensor columns). Both are drawn
    overlaid, in the same world frame, so the two shapes can be compared
    directly.

No third-party dependencies -- pure Python + the stdlib csv module,
consistent with the rest of this repo's tooling.

Usage:
    python3 tools/plot_track_csv.py <path/to.csv> [-o output.svg]
"""

import argparse
import csv
import math
import os


def read_rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def bbox(points):
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    return min(xs), min(ys), max(xs), max(ys)


def nice_grid_step(span, target_lines=6):
    if span <= 0:
        return 1.0
    raw = span / target_lines
    magnitude = 10 ** math.floor(math.log10(raw))
    for mult in (1, 2, 5, 10):
        step = mult * magnitude
        if step >= raw:
            return step
    return 10 * magnitude


class Canvas:
    def __init__(self, all_points, width=1000, height=700, margin=60):
        self.width, self.height, self.margin = width, height, margin
        x0, y0, x1, y1 = bbox(all_points)
        pad_x = (x1 - x0) * 0.03 or 10
        pad_y = (y1 - y0) * 0.03 or 10
        self.x0, self.y0, self.x1, self.y1 = x0 - pad_x, y0 - pad_y, x1 + pad_x, y1 + pad_y
        w = self.x1 - self.x0
        h = self.y1 - self.y0
        self.scale = min((width - 2 * margin) / w, (height - 2 * margin) / h)

    def tf(self, x, y):
        # World is mm, y-up by this project's convention (DESIGN.md SS2's
        # rotation math). SVG y grows downward, so flip here rather than
        # asking every caller to think about it.
        sx = self.margin + (x - self.x0) * self.scale
        sy = self.height - (self.margin + (y - self.y0) * self.scale)
        return sx, sy

    def polyline(self, points, color, width=1.6, dash=None, opacity=1.0):
        pts = " ".join("%.2f,%.2f" % self.tf(x, y) for x, y in points)
        dash_attr = ' stroke-dasharray="%s"' % dash if dash else ""
        return ('<polyline points="%s" fill="none" stroke="%s" stroke-width="%.2f" '
                'opacity="%.2f"%s stroke-linejoin="round"/>') % (pts, color, width, opacity, dash_attr)

    def marker(self, x, y, color, r=5, shape="circle"):
        sx, sy = self.tf(x, y)
        if shape == "square":
            return '<rect x="%.2f" y="%.2f" width="%.1f" height="%.1f" fill="%s"/>' % (sx - r, sy - r, 2 * r, 2 * r, color)
        return '<circle cx="%.2f" cy="%.2f" r="%.1f" fill="%s"/>' % (sx, sy, r, color)

    def grid_and_scalebar(self):
        parts = []
        step = nice_grid_step(self.x1 - self.x0)
        gx = math.ceil(self.x0 / step) * step
        while gx <= self.x1:
            sx, _ = self.tf(gx, self.y0)
            parts.append('<line x1="%.2f" y1="%d" x2="%.2f" y2="%d" stroke="#e5e5e5" stroke-width="1"/>'
                         % (sx, self.margin, sx, self.height - self.margin))
            gx += step
        step_y = nice_grid_step(self.y1 - self.y0)
        gy = math.ceil(self.y0 / step_y) * step_y
        while gy <= self.y1:
            _, sy = self.tf(self.x0, gy)
            parts.append('<line x1="%d" y1="%.2f" x2="%d" y2="%.2f" stroke="#e5e5e5" stroke-width="1"/>'
                         % (self.margin, sy, self.width - self.margin, sy))
            gy += step_y

        bar_mm = nice_grid_step(self.x1 - self.x0, target_lines=4)
        bx0, by = self.margin, self.height - 25
        bx1 = bx0 + bar_mm * self.scale
        parts.append('<line x1="%.2f" y1="%.2f" x2="%.2f" y2="%.2f" stroke="black" stroke-width="2"/>' % (bx0, by, bx1, by))
        parts.append('<text x="%.2f" y="%.2f" font-size="12" font-family="monospace">%g mm</text>'
                     % (bx0, by - 6, bar_mm))
        return "\n".join(parts)


def legend(entries, x, y):
    # entries: list of (color, label, dash_or_None)
    parts = ['<g font-family="sans-serif" font-size="13">']
    for i, (color, label, dash) in enumerate(entries):
        ly = y + i * 22
        if dash:
            parts.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="2.5" stroke-dasharray="%s"/>'
                         % (x, ly, x + 28, ly, color, dash))
        else:
            parts.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="2.5"/>'
                         % (x, ly, x + 28, ly, color))
        parts.append('<text x="%d" y="%d" dominant-baseline="middle">%s</text>' % (x + 36, ly, label))
    parts.append("</g>")
    return "\n".join(parts)


LAP_COLORS = ["#1f77b4", "#d62728", "#2ca02c", "#9467bd", "#ff7f0e", "#17becf"]


def render_firmware_csv(rows, title):
    laps = {}
    for r in rows:
        laps.setdefault(int(r["lap"]), []).append((float(r["x_mm"]), float(r["y_mm"])))

    all_points = [p for pts in laps.values() for p in pts] or [(0, 0)]
    c = Canvas(all_points)

    body = [c.grid_and_scalebar()]
    entries = []
    for lap_num in sorted(laps):
        pts = laps[lap_num]
        if lap_num == 0:
            color, dash, label = "#999999", "5,4", "lap 0 (pre-tape rollout, arbitrary origin)"
        else:
            color = LAP_COLORS[(lap_num - 1) % len(LAP_COLORS)]
            dash, label = None, "lap %d (%d samples)" % (lap_num, len(pts))
        body.append(c.polyline(pts, color, dash=dash))
        entries.append((color, label, dash))

    body.append(c.marker(0, 0, "black", r=5, shape="square"))
    entries.append(("black", "tape / origin (0,0)", None))
    body.append(legend(entries, c.margin, c.margin))
    return wrap_svg(c, body, title)


def render_sim_csv(rows, title):
    gt = [(float(r["gt_x_mm"]), float(r["gt_y_mm"])) for r in rows]
    gt0x, gt0y = gt[0]
    # main.py's (x,y) frame has its own x-axis aligned to the car's *initial*
    # heading (DESIGN.md SS6: "theta=0 = heading the car is sitting at when
    # this starts"), not the world/SVG's absolute X axis -- overlaying it on
    # the world-frame ground truth needs that fixed initial-heading rotation
    # applied first, or the two paths compare in different frames and look
    # wildly divergent despite the reconstruction actually tracking the real
    # shape reasonably well (this is what a first, un-rotated version of this
    # function showed -- a frame bug, not a fusion-algorithm one).
    heading0 = math.radians(float(rows[0]["gt_heading_deg"]))
    ch, sh = math.cos(heading0), math.sin(heading0)
    recon = []
    for r in rows:
        rx, ry = float(r["recon_x_mm"]), float(r["recon_y_mm"])
        recon.append((rx * ch - ry * sh + gt0x, rx * sh + ry * ch + gt0y))

    c = Canvas(gt + recon)
    body = [c.grid_and_scalebar()]
    body.append(c.polyline(gt, "#444444", width=2.0))
    body.append(c.polyline(recon, "#d62728", width=1.6, dash="6,3"))
    body.append(c.marker(gt0x, gt0y, "black", r=5, shape="square"))

    entries = [
        ("#444444", "ground truth (source track SVG)", None),
        ("#d62728", "reconstructed (main.py fusion math on synthetic sensors)", "6,3"),
        ("black", "tape / lap start", None),
    ]
    body.append(legend(entries, c.margin, c.margin))
    return wrap_svg(c, body, title)


def wrap_svg(c, body_parts, title):
    return """<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d">
<rect width="100%%" height="100%%" fill="white"/>
<text x="%d" y="24" font-family="sans-serif" font-size="16" font-weight="bold">%s</text>
%s
</svg>
""" % (c.width, c.height, c.width, c.height, c.margin, title, "\n".join(body_parts))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("csv_path")
    ap.add_argument("-o", "--output", help="output SVG path (default: <input>.svg)")
    args = ap.parse_args()

    rows = read_rows(args.csv_path)
    if not rows:
        raise SystemExit("CSV has no data rows: %s" % args.csv_path)

    fieldnames = set(rows[0].keys())
    title = os.path.basename(args.csv_path)

    if {"gt_x_mm", "recon_x_mm"} <= fieldnames:
        svg = render_sim_csv(rows, title + " (simulator: ground truth vs. reconstructed)")
    elif {"x_mm", "y_mm", "lap"} <= fieldnames:
        svg = render_firmware_csv(rows, title + " (firmware log, per-lap path)")
    else:
        raise SystemExit(
            "Unrecognized CSV columns: %s\n"
            "Expected either the firmware log shape (x_mm,y_mm,theta_rad,lap) "
            "or the simulator shape (gt_x_mm,gt_y_mm,recon_x_mm,recon_y_mm)." % sorted(fieldnames)
        )

    out_path = args.output or (os.path.splitext(args.csv_path)[0] + ".svg")
    with open(out_path, "w") as f:
        f.write(svg)
    print("Wrote %s (%d rows plotted)" % (out_path, len(rows)))


if __name__ == "__main__":
    main()
