"""Generate a CSV of the sensor data we'd *expect* to see (PMW3360 + ICM-42688-P
+ IR lap sensor) from one lap of the real Bolton club track (tmp/bolton-track.svg),
driven on one of the two center lanes, anti-clockwise, at a steady ~6V pace.

This is a synthetic-data generator, not firmware -- it runs on a desktop with
plain Python (no MicroPython/hardware dependencies) so it can be re-run to
explore other lanes/speeds/paces. See DESIGN.md SS2 and SS6 for the fusion math
this mirrors, and main.py for the firmware it's meant to be a test vector for.

Method
------
1. Parse the four lane paths out of the SVG (they're already polylines --
   M/L commands only, no curves -- so no curve-fitting is needed).
2. Pick one of the two geometrically-central lanes as "a center slot".
3. Scale the drawing to real units using the track's stated lap length
   (118 ft = 35,966.4 mm) applied to the chosen lane's own path length.
4. Orient the lane for anti-clockwise travel (as drawn/viewed on the plan,
   SVG y-down) and rotate it so index 0 is the start of the long straight.
5. Build a curvature-limited speed profile (lateral-grip-limited cornering,
   accel/brake-limited elsewhere), then uniformly rescale it to hit a target
   lap time -- this preserves the corner-vs-straight speed *shape* implied by
   the track geometry while pacing the whole lap for a steady, non-flooring
   throttle setting.
6. Walk the lap at 100 Hz (10 ms ticks), and at each tick synthesize what the
   PMW3360 (lever-arm-corrected per main.py's convention, run in reverse),
   ICM-42688-P gyro/accel, and IR reflectance sensor would actually report,
   including a straight-track lateral "wander" (the guide floating in the
   4 mm slot against a ~1 mm guide) and realistic sensor noise/bias.
7. As a sanity check, re-run main.py's own fusion math over the synthesized
   (noisy) sensor columns and compare the reconstructed path back against
   ground truth -- see the printed summary for the result.
"""

import csv
import math
import random
import re

random.seed(42)

SVG_PATH = "tmp/bolton-track.svg"
OUT_CSV = "sim/expected_track_run.csv"

LAP_LENGTH_MM = 118 * 0.3048 * 1000.0   # 118 ft, as stated for this track
TARGET_LAP_TIME_S = 12.5                # "12 seconds (or more)"
DT_S = 0.010                             # 100 Hz poll rate
CPI = 3000.0                             # matches pmw3360.py's default
COUNTS_PER_MM = CPI / 25.4
LEVER_ARM_MM = 18.0                      # matches main.py

TAPE_OFFSET_BEFORE_STRAIGHT_MM = 500.0   # "about half a meter from the start of the long straight"
TAPE_WIDTH_MM = 12.0                     # assumed width of the reflective start/finish tape
WANDER_AMPLITUDE_MM = 1.5                # slot width 4mm, guide ~1mm -> +-1.5mm play
WANDER_WAVELENGTH_MM = 300.0             # assumed guide-chatter spatial period

V_TOP_MS = 3.2          # m/s, straight-line pace at a steady ~6V throttle
LAT_ACCEL_MAX_G = 0.45  # assumed lane grip limit in cornering
LONG_ACCEL_MS2 = 2.5    # m/s^2, assumed accel capability at 6V
BRAKE_ACCEL_MS2 = 3.5   # m/s^2, assumed off-throttle/drag deceleration

GYRO_NOISE_RMS_DPS = 0.05
GYRO_BIAS_DPS = 0.30      # a deliberately modest, realistic uncalibrated bias
ACCEL_NOISE_RMS_G = 0.01
OPTICAL_NOISE_RMS_COUNTS = 1.0
IR_BASELINE = 4000
IR_BASELINE_NOISE = 200
IR_TAPE_LEVEL = 45000
LAP_THRESHOLD = 30000     # matches main.py


def parse_lanes(svg_path):
    text = open(svg_path).read()
    lanes = {}
    for d, color in re.findall(r'<path d="([^"]+)" fill="none" stroke="([a-z]+)"', text):
        tokens = d.replace(",", " ").split()
        pts, i = [], 0
        while i < len(tokens):
            if tokens[i] in ("M", "L"):
                pts.append((float(tokens[i + 1]), float(tokens[i + 2])))
                i += 3
            else:
                i += 1
        if pts[0] == pts[-1]:
            pts.pop()  # drop duplicate closing point, we treat it as a closed polygon
        lanes[color] = pts
    return lanes


def polygon_length(pts):
    n = len(pts)
    return sum(math.dist(pts[i], pts[(i + 1) % n]) for i in range(n))


def shoelace(pts):
    n = len(pts)
    return 0.5 * sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1] for i in range(n))


def pick_center_lane(lanes):
    by_length = sorted(lanes.items(), key=lambda kv: polygon_length(kv[1]))
    # 4 lanes -> the two middle ones (by path length) are the "center slots"
    return by_length[1]  # (color, pts) -- the inner of the two center lanes


def orient_and_rotate(pts):
    # Anti-clockwise "as drawn" (SVG y increases downward, so this is the
    # opposite sign convention from a standard y-up CCW shoelace check).
    if shoelace(pts) > 0:
        pts = pts[::-1]
    n = len(pts)
    seg_len = [math.dist(pts[i], pts[(i + 1) % n]) for i in range(n)]
    long_straight_start = seg_len.index(max(seg_len))
    return pts[long_straight_start:] + pts[:long_straight_start]


def build_arclength_table(pts_mm):
    n = len(pts_mm)
    cum = [0.0] * (n + 1)
    for i in range(n):
        cum[i + 1] = cum[i] + math.dist(pts_mm[i], pts_mm[(i + 1) % n])
    return cum  # cum[n] == total lap length


def point_at(s, pts_mm, cum):
    # Position only -- the raw polyline's own segments are kept exactly (its
    # source flattening already subdivides finely wherever the real curve is
    # tight), so this is a faithful sample of the true track shape.
    n = len(pts_mm)
    total = cum[n]
    s = s % total
    lo, hi = 0, n
    while lo < hi:
        mid = (lo + hi) // 2
        if cum[mid + 1] <= s:
            lo = mid + 1
        else:
            hi = mid
    i = lo
    p0, p1 = pts_mm[i], pts_mm[(i + 1) % n]
    seg_len = cum[i + 1] - cum[i]
    t = 0.0 if seg_len < 1e-9 else (s - cum[i]) / seg_len
    return p0[0] + t * (p1[0] - p0[0]), p0[1] + t * (p1[1] - p0[1])


HEADING_WINDOW_MM = 60.0  # half-window for the centered-difference heading estimate below
# CAVEAT: this windowed estimate is a synthesis convenience (see heading_at()'s
# docstring), not a real gyro -- isolation testing (bias=0, all sensor noise=0)
# showed it alone produces a ~750mm reconstructed-vs-ground-truth closing error
# over one lap, from smoothing the *true* instantaneous heading into something
# systematically different over a full lap of accumulated turns. That's an
# artifact of this script's own heading-synthesis method, not a property of
# main.py's fusion algorithm or of a real gyro -- do not attribute the
# "closing error" this script prints to gyro bias without subtracting this
# baseline first (see the gyro-bias calibration validation this was found
# while doing, DESIGN.md SS6).


def heading_at(s, pts_mm, cum, half_window=HEADING_WINDOW_MM):
    # A raw per-vertex segment direction is a step function -- sampled at a
    # fixed vertex it reads as an instantaneous heading jump (a delta-function
    # spike in gyro rate) that a real chassis with continuous curvature can't
    # produce. Averaging the direction over a short arc-length window removes
    # that discretization artifact without needing to resample the geometry.
    x1, y1 = point_at(s - half_window, pts_mm, cum)
    x2, y2 = point_at(s + half_window, pts_mm, cum)
    return math.atan2(y2 - y1, x2 - x1)


def radius_at(s, pts_mm, cum, ds=10.0):
    h1 = heading_at(s - ds, pts_mm, cum)
    h2 = heading_at(s + ds, pts_mm, cum)
    dh = math.atan2(math.sin(h2 - h1), math.cos(h2 - h1))  # wrap to (-pi, pi]
    if abs(dh) < 1e-9:
        return float("inf")
    return abs(2 * ds / dh)


def build_speed_profile(pts_mm, cum, ds_grid=20.0):
    total = cum[len(pts_mm)]
    n_grid = int(total // ds_grid) + 1
    s_grid = [i * ds_grid for i in range(n_grid)]
    radii = [radius_at(s, pts_mm, cum) for s in s_grid]

    g = 9.81
    a_lat = LAT_ACCEL_MAX_G * g  # m/s^2
    v_curve = []
    for r_mm in radii:
        r_m = r_mm / 1000.0
        v = V_TOP_MS if math.isinf(r_mm) else min(V_TOP_MS, math.sqrt(a_lat * r_m))
        v_curve.append(v)

    ds_m = ds_grid / 1000.0
    v_fwd = list(v_curve)
    for _ in range(2):  # two passes around the loop so the wraparound converges
        for i in range(n_grid):
            prev = v_fwd[i - 1] if i > 0 else v_fwd[-1]
            v_fwd[i] = min(v_curve[i], math.sqrt(prev ** 2 + 2 * LONG_ACCEL_MS2 * ds_m))
    v_final = list(v_fwd)
    for _ in range(2):
        for i in range(n_grid - 1, -1, -1):
            nxt = v_final[i + 1] if i < n_grid - 1 else v_final[0]
            v_final[i] = min(v_fwd[i], math.sqrt(nxt ** 2 + 2 * BRAKE_ACCEL_MS2 * ds_m))

    # integrate to get lap time at this pace, then uniformly rescale speed to
    # hit TARGET_LAP_TIME_S while keeping the corner/straight speed *shape*
    t_raw = 0.0
    for i in range(n_grid):
        v_avg = (v_final[i] + v_final[(i + 1) % n_grid]) / 2.0
        t_raw += ds_m / v_avg
    scale = t_raw / TARGET_LAP_TIME_S
    v_final = [v * scale for v in v_final]

    return s_grid, v_final, radii, ds_grid


def build_time_table(s_grid, v_final, total_mm):
    ds_m = (s_grid[1] - s_grid[0]) / 1000.0
    n_grid = len(s_grid)
    t_grid = [0.0] * n_grid
    for i in range(1, n_grid):
        v_avg = (v_final[i - 1] + v_final[i]) / 2.0
        t_grid[i] = t_grid[i - 1] + ds_m / v_avg
    v_avg_wrap = (v_final[-1] + v_final[0]) / 2.0
    lap_time = t_grid[-1] + ds_m / v_avg_wrap
    return t_grid, lap_time


def s_at_time(t_query, s_grid, t_grid, lap_time, total_mm):
    n = len(s_grid)
    if t_query >= t_grid[-1]:
        # last grid segment wraps to (s_grid[0] + total_mm, lap_time)
        frac = (t_query - t_grid[-1]) / (lap_time - t_grid[-1]) if lap_time > t_grid[-1] else 0.0
        return s_grid[-1] + frac * (total_mm - s_grid[-1])
    lo, hi = 0, n - 1
    while lo < hi:
        mid = (lo + hi) // 2
        if t_grid[mid + 1] <= t_query:
            lo = mid + 1
        else:
            hi = mid
    i = lo
    frac = 0.0 if t_grid[i + 1] == t_grid[i] else (t_query - t_grid[i]) / (t_grid[i + 1] - t_grid[i])
    return s_grid[i] + frac * (s_grid[i + 1] - s_grid[i])


def gauss(rms):
    return random.gauss(0.0, rms) if rms > 0 else 0.0


def main():
    lanes = parse_lanes(SVG_PATH)
    color, raw_pts = pick_center_lane(lanes)
    total_svg_len = polygon_length(raw_pts)
    scale = LAP_LENGTH_MM / total_svg_len

    oriented = orient_and_rotate(raw_pts)
    pts_mm = [(x * scale, y * scale) for x, y in oriented]
    cum = build_arclength_table(pts_mm)
    total_mm = cum[-1]

    s_grid, v_final, radii, ds_grid = build_speed_profile(pts_mm, cum)
    t_grid, lap_time = build_time_table(s_grid, v_final, total_mm)

    S0 = total_mm - TAPE_OFFSET_BEFORE_STRAIGHT_MM  # tape is 500mm before index 0

    n_ticks = int(lap_time / DT_S) + 2
    rows = []
    theta_prev = None
    s_prev = None
    x_recon = y_recon = theta_recon = 0.0  # firmware-style reconstruction, for validation
    lap_count = 0
    ir_above = False
    last_lap_ms = -10_000

    finite_radii = [r for r in radii if not math.isinf(r)]
    min_radius_mm = min(finite_radii)

    for k in range(n_ticks):
        t = k * DT_S
        if t > lap_time:
            break
        s_abs = S0 + s_at_time(t, s_grid, t_grid, lap_time, total_mm)
        x_path, y_path = point_at(s_abs, pts_mm, cum)
        heading = heading_at(s_abs, pts_mm, cum)

        wander = WANDER_AMPLITUDE_MM * math.sin(2 * math.pi * s_abs / WANDER_WAVELENGTH_MM)
        wander_slope = (WANDER_AMPLITUDE_MM * 2 * math.pi / WANDER_WAVELENGTH_MM) * math.cos(2 * math.pi * s_abs / WANDER_WAVELENGTH_MM)
        nx, ny = -math.sin(heading), math.cos(heading)  # left-hand normal
        x_true = x_path + wander * nx
        y_true = y_path + wander * ny
        theta_true = heading + math.atan(wander_slope)

        v_local = v_final[int((s_abs % total_mm) // ds_grid) % len(v_final)]

        if theta_prev is None:
            theta_prev = theta_true
            s_prev = s_abs
        raw_dtheta = theta_true - theta_prev
        dtheta_true = math.atan2(math.sin(raw_dtheta), math.cos(raw_dtheta))  # wrap across the atan2 branch cut
        theta_prev, s_prev = theta_true, s_abs

        gz_dps_true = math.degrees(dtheta_true) / DT_S
        gz_dps_meas = gz_dps_true + GYRO_BIAS_DPS + gauss(GYRO_NOISE_RMS_DPS)

        v_forward_body = v_local * 1000.0  # mm/s
        v_lateral_body = wander_slope * v_local * 1000.0  # mm/s, d(wander)/dt = d(wander)/ds * ds/dt

        dx_pivot = v_forward_body * DT_S
        dy_pivot = v_lateral_body * DT_S
        dx_sensor = dx_pivot
        dy_sensor = dy_pivot + dtheta_true * LEVER_ARM_MM  # forward kinematics, inverse of main.py's correction

        pmw_dx = round(dx_sensor * COUNTS_PER_MM + gauss(OPTICAL_NOISE_RMS_COUNTS))
        pmw_dy = round(dy_sensor * COUNTS_PER_MM + gauss(OPTICAL_NOISE_RMS_COUNTS))

        r_idx = int((s_abs % total_mm) // ds_grid) % len(radii)
        r_here = radii[r_idx]
        ay_g = 0.0 if math.isinf(r_here) else (v_local ** 2) / (r_here / 1000.0) / 9.81
        ax_g = ((v_final[(int((s_abs % total_mm) // ds_grid) + 1) % len(v_final)] - v_local) / (ds_grid / 1000.0 / max(v_local, 0.05))) / 9.81 if v_local > 0.05 else 0.0
        ax_meas = ax_g + gauss(ACCEL_NOISE_RMS_G)
        ay_meas = ay_g + gauss(ACCEL_NOISE_RMS_G)
        az_meas = 1.0 + gauss(ACCEL_NOISE_RMS_G)

        in_tape = ((s_abs - S0) % total_mm) < TAPE_WIDTH_MM
        ir_val = IR_TAPE_LEVEL + int(gauss(500)) if in_tape else IR_BASELINE + int(gauss(IR_BASELINE_NOISE))
        ir_val = max(0, min(65535, ir_val))

        t_ms = round(t * 1000)
        if ir_val > LAP_THRESHOLD and not ir_above and (t_ms - last_lap_ms) > 1000:
            ir_above = True
            last_lap_ms = t_ms
            lap_count += 1
        elif ir_val <= LAP_THRESHOLD:
            ir_above = False

        # --- firmware-style reconstruction from the noisy sensor columns, for validation ---
        dtheta_recon = math.radians(gz_dps_meas) * DT_S
        theta_recon += dtheta_recon
        dx_pivot_r = pmw_dx / COUNTS_PER_MM
        dy_pivot_r = (pmw_dy / COUNTS_PER_MM) - dtheta_recon * LEVER_ARM_MM
        ct, st = math.cos(theta_recon), math.sin(theta_recon)
        x_recon += dx_pivot_r * ct - dy_pivot_r * st
        y_recon += dx_pivot_r * st + dy_pivot_r * ct

        rows.append(dict(
            t_ms=t_ms,
            pmw_dx_counts=pmw_dx, pmw_dy_counts=pmw_dy,
            gyro_z_dps=round(gz_dps_meas, 4),
            accel_x_g=round(ax_meas, 4), accel_y_g=round(ay_meas, 4), accel_z_g=round(az_meas, 4),
            ir_adc=ir_val,
            gt_x_mm=round(x_true, 2), gt_y_mm=round(y_true, 2), gt_heading_deg=round(math.degrees(theta_true), 2),
            gt_speed_mm_s=round(v_local * 1000.0, 1),
            recon_x_mm=round(x_recon, 2), recon_y_mm=round(y_recon, 2),
        ))

    with open(OUT_CSV, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    dx_err = rows[-1]["recon_x_mm"] - rows[-1]["gt_x_mm"] + rows[0]["gt_x_mm"]
    dy_err = rows[-1]["recon_y_mm"] - rows[-1]["gt_y_mm"] + rows[0]["gt_y_mm"]
    err_mag = math.hypot(dx_err, dy_err)

    tape_ticks = sum(1 for r in rows if r["ir_adc"] > LAP_THRESHOLD)

    print("Chosen lane            : %s (of blue/lime/yellow/red)" % color)
    print("Lap length             : %.1f mm (%.2f ft)" % (total_mm, total_mm / 304.8))
    print("Scale factor            : %.4f mm/svg-unit" % scale)
    print("Tightest corner radius  : %.0f mm" % min_radius_mm)
    print("Target lap time         : %.2f s (achieved %.2f s)" % (TARGET_LAP_TIME_S, lap_time))
    print("Peak speed after pacing : %.2f m/s" % max(v_final))
    print("Ticks generated         : %d (%d ms)" % (len(rows), rows[-1]["t_ms"]))
    print("Samples with IR > threshold (lap tape hits): %d" % tape_ticks)
    print("Lap-detector fired      : %d time(s)" % lap_count)
    print("Reconstructed-vs-ground-truth closing error after 1 lap: %.1f mm" % err_mag)
    print("  (includes a ~750mm heading-synthesis baseline from this script's own windowed")
    print("   heading estimate -- see the HEADING_WINDOW_MM caveat above -- not just gyro bias)")


if __name__ == "__main__":
    main()
