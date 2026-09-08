"""Combine several already-corrected per-lane vector paths into one shared-frame track map.

This is the "combining half" DESIGN.md SS9 describes and SS8 lists as an open
item: each lane is mapped by its own separate recording run (SS9's "Why this
has to be N independent runs, not one"), so each lane's (x, y) path starts out
in its OWN local frame -- origin at the shared tape crossing, x-axis aligned to
that car's own heading at power-up. SS9's design is that with the tape placed
on a straight or gentle curve, every lane's run shares (approximately) both
that crossing point AND that initial heading, so the only thing separating one
lane's frame from another's is the lateral offset between them at the tape
cross-section -- a distance a human measures once with a ruler/caliper, not
something the onboard sensors can infer (a guide-pin-constrained car in lane A
has no way to sense where lane B is). Given that measured offset per lane,
combining is exactly: shift each lane's path sideways (perpendicular to the
shared heading, i.e. along its own y-axis) by its own offset, and every lane
lands in one common frame for free -- no rotation, no rescaling.

This does NOT attempt to derive or sanity-check the offsets themselves -- get
those with a ruler at the tape line, once, as SS9 describes. Garbage in
(a wrong or missing measurement) is garbage out (a lane placed at the wrong
spacing) -- there is no way to detect that from the vector paths alone, which
is exactly why SS9 keeps this a human measurement rather than an inferred one.

Input: each lane is one CSV already produced by this project's existing
per-lane pipeline (BRINGUP.md Stage 11) --
    - the SS6 "averaged lap shape" from closed_loop_correct.py --average-out
      (columns: frac,x_mm,y_mm) -- the normal, recommended input, since it's
      already corrected and noise-averaged; or
    - a plain two-column (x_mm,y_mm) CSV, for a path that arrived some other
      way (e.g. hand-digitized from a plan).
A raw multi-lap firmware/corrected log (t_ms,x_mm,y_mm,theta_rad,lap) is NOT
accepted directly -- run it through closed_loop_correct.py first (with
--average-out, or extract one lap) so there's a single unambiguous path per
lane to combine.

Usage:
    python3 tools/combine_lanes.py red:sim/expected_track_run_lane_red_avg.csv:0 \\
                                   blue:sim/expected_track_run_lane_blue_avg.csv:38.5 \\
                                   -o combined_track.svg --csv combined_track.csv

Each positional argument is LABEL:PATH:OFFSET_MM -- OFFSET_MM is this lane's
signed lateral offset from the reference (0mm) lane, measured perpendicular to
the shared start heading at the tape line (SS9). Which sign is "left" vs.
"right" doesn't matter as long as it's used consistently across all lanes
measured at the same cross-section.
"""

import argparse
import csv
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from plot_track_csv import Canvas, LAP_COLORS, legend, wrap_svg  # noqa: E402


def read_lane_path(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    if not rows:
        raise SystemExit("%s: no data rows" % path)
    fieldnames = set(rows[0].keys())
    if "lap" in fieldnames:
        raise SystemExit(
            "%s: looks like a raw multi-lap log (has a 'lap' column). "
            "Run it through closed_loop_correct.py first -- ideally with "
            "--average-out -- and pass that single-path CSV here instead." % path
        )
    if {"x_mm", "y_mm"} <= fieldnames:
        return [(float(r["x_mm"]), float(r["y_mm"])) for r in rows]
    raise SystemExit(
        "%s: unrecognized columns %s -- expected the closed_loop_correct.py "
        "--average-out shape (frac,x_mm,y_mm) or a plain (x_mm,y_mm) CSV."
        % (path, sorted(fieldnames))
    )


def parse_lane_spec(spec):
    parts = spec.split(":")
    if len(parts) != 3:
        raise SystemExit(
            "Bad lane spec %r -- expected LABEL:PATH:OFFSET_MM" % spec
        )
    label, path, offset_str = parts
    try:
        offset_mm = float(offset_str)
    except ValueError:
        raise SystemExit("Bad offset in lane spec %r -- OFFSET_MM must be a number" % spec)
    return label, path, offset_mm


def path_length_m(points):
    return sum(math.dist(points[i - 1], points[i]) for i in range(1, len(points))) / 1000.0


def combine(lane_specs):
    """Returns a list of (label, offset_mm, points) with points already shifted
    into the shared frame (points is a list of (x_mm, y_mm))."""
    combined = []
    for label, path, offset_mm in lane_specs:
        points = read_lane_path(path)
        shifted = [(x, y + offset_mm) for x, y in points]
        combined.append((label, offset_mm, shifted))
    return combined


def write_csv(combined, out_path):
    with open(out_path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["lane", "x_mm", "y_mm"])
        for label, _offset_mm, points in combined:
            for x, y in points:
                w.writerow([label, round(x, 2), round(y, 2)])


def render_svg(combined, title):
    all_points = [p for _label, _offset_mm, points in combined for p in points] or [(0, 0)]
    c = Canvas(all_points)
    body = [c.grid_and_scalebar()]
    entries = []
    for i, (label, offset_mm, points) in enumerate(combined):
        color = LAP_COLORS[i % len(LAP_COLORS)]
        body.append(c.polyline(points, color))
        entries.append((color, "%s (offset %+.1f mm)" % (label, offset_mm), None))
    body.append(c.marker(0, 0, "black", r=5, shape="square"))
    entries.append(("black", "tape / shared origin (0,0)", None))
    body.append(legend(entries, c.margin, c.margin))
    return wrap_svg(c, body, title)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("lanes", nargs="+", metavar="LABEL:PATH:OFFSET_MM",
                     help="one per lane -- see the module docstring for the format")
    ap.add_argument("-o", "--output", default="combined_track.svg", help="output SVG path")
    ap.add_argument("--csv", help="also write the combined shared-frame path as a CSV (columns: lane,x_mm,y_mm)")
    args = ap.parse_args()

    lane_specs = [parse_lane_spec(s) for s in args.lanes]
    combined = combine(lane_specs)

    for label, offset_mm, points in combined:
        print("%s: offset %+.1f mm, %d points, length %.3f m" % (label, offset_mm, len(points), path_length_m(points)))

    with open(args.output, "w") as f:
        f.write(render_svg(combined, "Combined lane map (%d lanes)" % len(combined)))
    print("Wrote %s" % args.output)

    if args.csv:
        write_csv(combined, args.csv)
        print("Wrote %s" % args.csv)


if __name__ == "__main__":
    main()
