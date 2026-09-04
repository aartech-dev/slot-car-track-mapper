"""Offline closed-loop gyro-bias correction for a firmware track log.

Why this works without any firmware change: main.py's log already contains
everything needed. theta_rad accumulates continuously across the whole run
(main.py never resets it, only x/y), so the raw per-tick heading change
dtheta[i] = theta[i] - theta[i-1] is exactly recoverable from the CSV alone.
And since x[i],y[i] are theta[i] rotated body-frame motion accumulated onto
x[i-1],y[i-1] (DESIGN.md SS6's fusion loop), the per-tick body-frame
(dx_pivot, dy_pivot) is recoverable by inverse-rotating the logged position
delta by the logged theta[i]. Given those two per-tick quantities, a lap can
be fully re-integrated with a different (corrected) heading trace, without
ever needing the raw optical/gyro sensor columns.

The correction itself: one full lap is a closed curve, so its net heading
change is a known geometric quantity -- NOT a free parameter to guess. For a
simple, non-self-crossing loop it's +-360 degrees (+-1.0 "net turns"); for a
lane whose own path crosses itself once (common on tracks with a crossover
piece -- see the --net-turns help text for the distinction that matters
here), it can be different. Whatever it is, take the difference between that
known value and what the lap's own logged theta actually did, spread that
error evenly (per elapsed time, not per sample -- main.py's loop is
unthrottled, so dt is not constant) across the lap, and re-integrate.

This does NOT need to know the track's shape -- only the one number
(net turns) a human determines once, by inspecting the built track (or, if a
digital plan happens to exist, by computing it exactly -- see
sim/simulate_track_run.py's own use of this technique on tmp/bolton-track.svg
for how that's done, purely for validation there since defeats the purpose
of "mapping an unknown track" as an input to real mapping).

Usage:
    python3 tools/closed_loop_correct.py <track_log.csv> --net-turns N [-o out.csv]
"""

import argparse
import csv
import math

MIN_LAP_ROWS = 10  # shorter "laps" (e.g. a trailing partial segment) are passed through unchanged


def read_rows(path):
    with open(path, newline="") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["t_ms"] = int(r["t_ms"])
        r["x_mm"] = float(r["x_mm"])
        r["y_mm"] = float(r["y_mm"])
        r["theta_rad"] = float(r["theta_rad"])
        r["lap"] = int(r["lap"])
    return rows


def group_by_lap(rows):
    groups = []
    start = 0
    for i in range(1, len(rows) + 1):
        if i == len(rows) or rows[i]["lap"] != rows[start]["lap"]:
            groups.append(rows[start:i])
            start = i
    return groups


def lap_length_m(points):
    return sum(math.dist(points[i - 1], points[i]) for i in range(1, len(points))) / 1000.0


def resample_by_arclength(points, n_samples):
    """Resample a lap's (x,y) trace at n_samples evenly-spaced fractions of its
    own arc length -- lets laps of slightly different duration/speed be
    averaged point-for-point by *position along the lap*, not by time or
    sample index."""
    cum = [0.0]
    for i in range(1, len(points)):
        cum.append(cum[-1] + math.dist(points[i - 1], points[i]))
    total = cum[-1]
    out = []
    for k in range(n_samples):
        target = total * k / n_samples
        lo, hi = 0, len(cum) - 1
        while lo < hi:
            mid = (lo + hi) // 2
            if cum[mid + 1] < target:
                lo = mid + 1
            else:
                hi = mid
        i = min(lo, len(points) - 2)
        seg_len = cum[i + 1] - cum[i]
        t = 0.0 if seg_len < 1e-9 else (target - cum[i]) / seg_len
        x = points[i][0] + t * (points[i + 1][0] - points[i][0])
        y = points[i][1] + t * (points[i + 1][1] - points[i][1])
        out.append((x, y))
    return out, total


def correct_lap(segment, net_turns):
    n = len(segment)
    if n < MIN_LAP_ROWS:
        return list(segment), None

    expected_turn_rad = net_turns * 2 * math.pi
    measured_turn_rad = segment[-1]["theta_rad"] - segment[0]["theta_rad"]
    total_time_s = (segment[-1]["t_ms"] - segment[0]["t_ms"]) / 1000.0
    if total_time_s <= 0:
        return list(segment), None
    correction_rate_rad_s = (measured_turn_rad - expected_turn_rad) / total_time_s

    out = [dict(segment[0])]
    theta_prev_corrected = segment[0]["theta_rad"]
    x_prev, y_prev = 0.0, 0.0
    for i in range(1, n):
        prev, cur = segment[i - 1], segment[i]
        dt = (cur["t_ms"] - prev["t_ms"]) / 1000.0
        dtheta_raw = cur["theta_rad"] - prev["theta_rad"]
        dtheta_corrected = dtheta_raw - correction_rate_rad_s * dt
        theta_cur_corrected = theta_prev_corrected + dtheta_corrected

        # Recover this tick's body-frame (dx_pivot, dy_pivot) by inverse-rotating
        # the ORIGINAL logged position delta by the ORIGINAL logged theta[i] --
        # that's the rotation main.py actually applied when it computed x[i],y[i].
        dx_world = cur["x_mm"] - prev["x_mm"]
        dy_world = cur["y_mm"] - prev["y_mm"]
        orig_theta_i = cur["theta_rad"]
        ct, st = math.cos(orig_theta_i), math.sin(orig_theta_i)
        dx_pivot = dx_world * ct + dy_world * st
        dy_pivot = -dx_world * st + dy_world * ct

        # Re-rotate that SAME body-frame motion using the corrected heading.
        cct, cst = math.cos(theta_cur_corrected), math.sin(theta_cur_corrected)
        x_cur = x_prev + dx_pivot * cct - dy_pivot * cst
        y_cur = y_prev + dx_pivot * cst + dy_pivot * cct

        row = dict(cur)
        row["x_mm"] = round(x_cur, 2)
        row["y_mm"] = round(y_cur, 2)
        row["theta_rad"] = round(theta_cur_corrected, 4)
        out.append(row)

        theta_prev_corrected, x_prev, y_prev = theta_cur_corrected, x_cur, y_cur

    return out, correction_rate_rad_s


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("csv_path")
    ap.add_argument("--net-turns", type=float, required=True, help=(
        "Net signed full rotations the DRIVEN LANE's own centerline makes over one lap "
        "(not the whole track's lane count or crossover count). +1.0 for a simple "
        "clockwise-as-measured loop with no self-crossing, -1.0 for the other direction. "
        "A lane-swap crossover piece (common, used to equalize lane lengths) does NOT "
        "usually change this -- each lane's own path is typically still a simple loop "
        "even though it crosses the OTHER lane there. Only a lane whose own centerline "
        "crosses ITSELF gets a different value (e.g. 0.0 for a single self-crossing, "
        "like a figure-8's lemniscate shape) -- determine this by inspecting the built "
        "track's driven lane specifically, or compute it exactly from a digital plan if "
        "one exists (see sim/simulate_track_run.py)."
    ))
    ap.add_argument("-o", "--output", help="output CSV path (default: <input>_corrected.csv)")
    ap.add_argument("--average-out", help=(
        "also resample every complete, corrected lap to a common arc-length "
        "parameterization and average them into one mean-lap-shape CSV at this "
        "path (columns: frac,x_mm,y_mm) -- needs 2+ qualifying laps. Treat this "
        "as a smoothed MAP SHAPE for visualization, not a more authoritative "
        "lap-length source than the per-lap mean printed above: it doesn't "
        "correct for small heading-orientation differences between laps before "
        "averaging, which can inflate its own length figure (seen in testing: "
        "~36.9m averaged vs. a ~36.35m per-lap mean on the same 5-lap dataset)."
    ))
    ap.add_argument("--average-samples", type=int, default=360, help=(
        "points per lap in --average-out's resampling (default 360, i.e. one per degree of lap progress)"
    ))
    args = ap.parse_args()

    rows = read_rows(args.csv_path)
    groups = group_by_lap(rows)

    out_rows = []
    lap_lengths_m = []
    corrected_lap_points = []  # for --average-out
    for seg in groups:
        lap_num = seg[0]["lap"]
        if lap_num == 0:
            print("lap 0 (rollout): %d rows, passed through unchanged" % len(seg))
            out_rows.extend(seg)
            continue
        corrected, rate = correct_lap(seg, args.net_turns)
        points = [(r["x_mm"], r["y_mm"]) for r in corrected]
        length_m = lap_length_m(points)
        if rate is None:
            print("lap %d: %d rows, too short to correct (< %d), passed through unchanged"
                  % (lap_num, len(seg), MIN_LAP_ROWS))
        else:
            print("lap %d: %d rows, correction = %.4f dps applied, length = %.3f m"
                  % (lap_num, len(seg), math.degrees(rate), length_m))
            lap_lengths_m.append(length_m)
            corrected_lap_points.append(points)
        out_rows.extend(corrected)

    out_path = args.output or (args.csv_path.rsplit(".", 1)[0] + "_corrected.csv")
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["t_ms", "x_mm", "y_mm", "theta_rad", "lap"])
        w.writeheader()
        for r in out_rows:
            w.writerow({k: r[k] for k in ["t_ms", "x_mm", "y_mm", "theta_rad", "lap"]})
    print("Wrote %s" % out_path)

    if lap_lengths_m:
        mean_len = sum(lap_lengths_m) / len(lap_lengths_m)
        spread = (max(lap_lengths_m) - min(lap_lengths_m)) if len(lap_lengths_m) > 1 else 0.0
        print("Lap length: mean %.3f m over %d lap(s) (min %.3f, max %.3f, spread %.3f m)"
              % (mean_len, len(lap_lengths_m), min(lap_lengths_m), max(lap_lengths_m), spread))

    if args.average_out:
        if len(corrected_lap_points) < 2:
            print("--average-out needs 2+ complete laps, only got %d -- skipped" % len(corrected_lap_points))
        else:
            n = args.average_samples
            resampled = [resample_by_arclength(pts, n)[0] for pts in corrected_lap_points]
            avg_points = []
            for k in range(n):
                ax = sum(r[k][0] for r in resampled) / len(resampled)
                ay = sum(r[k][1] for r in resampled) / len(resampled)
                avg_points.append((ax, ay))
            avg_length_m = lap_length_m(avg_points + [avg_points[0]])  # close the loop for the length figure
            with open(args.average_out, "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["frac", "x_mm", "y_mm"])
                for k, (x, y) in enumerate(avg_points):
                    w.writerow([round(k / n, 4), round(x, 2), round(y, 2)])
            print("Wrote %s (%d laps averaged, %d points, averaged length %.3f m)"
                  % (args.average_out, len(corrected_lap_points), n, avg_length_m))


if __name__ == "__main__":
    main()
