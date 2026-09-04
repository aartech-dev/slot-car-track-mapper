# Bring-Up Plan: Slot Car Track Mapper

Status: nothing in this build has touched real hardware yet — `DESIGN.md` is the rationale, `cad/`, `electronics/`, and the firmware (`main.py`, `pmw3360.py`, `icm42688.py`) are all first-pass artifacts with known placeholders (SROM firmware, `LAP_THRESHOLD`, several CAD dimensions). This plan sequences validation so each stage retires a specific set of unknowns before the next stage depends on them — and so the one irreversible step (cutting the donor chassis, §7) happens last, after everything it depends on has already been proven on the bench.

**Ground rule:** don't proceed past a stage's pass criteria on a "probably fine" — the whole point of staging is that a failure here is cheap to diagnose (one new variable) and expensive to diagnose three stages later (five new variables at once).

## Stage 0 — Prerequisites

**Parts for the electronics stages below (Stages 1–6):** Pico 2 W, PMW3360 breakout, ICM-42688-P breakout, IR reflectance module (TCRT5000/QRE1113-class), buck-boost regulator module, supercap, Schottky diodes ×2, resistor for R1, breadboard + jumper wires, USB cable — `BOM.md` is the complete, authoritative parts list (electronics, mechanical, consumables, with sourcing status for each) covering the whole build, including the mechanical parts (chassis, fixture material, guide pins, skid material, tape) not needed until Stages 7+.

**Tools:** multimeter (essential). A bench-adjustable DC supply is nice to have for Stage 2, but not required — the analog track controller you already have *is* a variable 0–18V DC source (that's literally its job), so it can double as one with the car disconnected.

**Software:** MicroPython firmware flashed onto the Pico 2 W, Thonny or `mpremote` for REPL access and file transfer.

**Before Stage 3 specifically:** source the real PMW3360 SROM firmware (see `pmw3360.py`'s docstring and `DESIGN.md` §3/§6 — the placeholder will not track). The known-good technique is the same one `a6_binary.py` already used for the ADNS-9800: take a verified open-source driver's firmware header (e.g. SunjunKim's PMW3360 Arduino library) and convert it to a Python byte array. Do this before Stage 3, not during it.

---

## Stage 1 — Pico 2 W solo bring-up

**Goal:** confirm the board and toolchain work before anything else depends on them.

**Procedure:** flash MicroPython, connect via Thonny/`mpremote`, confirm the REPL banner shows the expected MicroPython/board version. Run a trivial `Pin` toggle on the onboard LED.

**Pass:** REPL connects reliably; LED blinks.

**If it fails:** don't touch sensors yet — this is a flashing/driver/cable problem, isolate it here.

---

## Stage 2 — Power subsystem bench validation (independent of firmware — can run in parallel with Stages 3–6)

**Goal:** validate the regulator + R1/D2/C1 sub-circuit (`electronics/electronics.kicad_sch`, `DESIGN.md` §4) against a *real* variable input, and get the real numbers needed to close out that section's open items.

**Setup:** regulator + D1 + R1 + D2 + C1 built on breadboard per the schematic, fed from the track controller (car disconnected) so input voltage sweeps the real 0–18V-ish range. Load the output with the Pico (running, drawing its normal current) rather than a dummy resistor — real current draw is what actually matters here.

**Procedure and what to record:**
1. Sweep the controller trigger through its range; multimeter on regulator output. Record output voltage at several trigger positions, and find the trigger position where regulation first fails (input too low).
2. Measure the regulator's actual current limit if its datasheet doesn't already state one you trust (slowly increase load, or check the datasheet) — this is the number `DESIGN.md` §4 flags as missing for properly sizing R1.
3. Time the supercap charging from empty to steady-state at full trigger. Compare against the ~24s prediction (R1=4.7Ω, C1=1F). If it's very different, R1 or C1 need updating together, not independently (§4 explains why).
4. With the cap charged and the Pico running, cut input power and time how long output stays above ~3V. Compare against the ride-through estimate in §4.
5. Briefly test reverse polarity at the input (low current, be ready to disconnect) and confirm D1 protects the regulator.

**Pass:** regulator holds ~5V down to a throttle position you're comfortable calling "the floor"; charge and ride-through times are in the right ballpark or you've recorded real numbers to update `DESIGN.md`/the schematic with; reverse polarity doesn't damage anything.

**If it fails:** this is bench-testable in complete isolation from every other stage — fix it here, not after it's built into the fixture.

---

## Stage 3 — PMW3360 solo bring-up (breadboard)

**Goal:** get real SROM firmware in and confirm the sensor actually tracks, before it's anywhere near the car.

**Setup:** PMW3360 breakout wired to the Pico exactly per the schematic (GPIO10-13 SPI0, GPIO14 motion interrupt — currently unused/polled), powered from USB for now (not the regulator yet).

**Procedure:**
1. Before touching SROM: read `PRODUCT_ID` (register 0x00) over SPI. This is a fixed silicon value and should read `0x42` regardless of SROM state — if it doesn't, it's a wiring/SPI problem, not an SROM problem. Isolate that distinction here.
2. Drop the real SROM firmware into `pmw3360.py` (Stage 0). Run `PMW3360.begin()`; confirm it doesn't raise, and that the SROM ID it returns is non-zero.
3. Slide the sensor by hand over a real surface and poll `read_motion()`. Confirm non-zero, sensible-sign `(dx, dy)` that match the direction you actually moved it.
4. Calibrate CPI: move the sensor a measured distance (e.g. 100mm along a ruler) and compare accumulated counts against the nominal CPI setting in `pmw3360.py`. Adjust if the real conversion factor is off.

**Pass:** motion counts track real hand movement in the correct direction and roughly the correct magnitude.

**If it fails after real SROM is in:** check the axis/sign assumption before assuming the driver is broken — a mirrored or rotated sensor lens will report axes that don't match intuition without being "wrong."

---

## Stage 4 — ICM-42688-P solo bring-up (breadboard)

**Goal:** confirm the IMU driver and get the real gyro sign, before the fusion loop depends on it.

**Setup:** breakout wired per schematic (GPIO4/5 I2C0, GPIO6 interrupt — currently unused/polled), USB power.

**Procedure:**
1. `ICM42688.begin()` — confirm `WHO_AM_I` reads `0x47`.
2. At rest, read `read_accel_g()` — confirm one axis reads ~1g (gravity) and the other two read ~0g, consistent with however the breakout happens to be lying flat on the bench.
3. Rotate the board by hand around what will be the vertical (yaw) axis once mounted; watch `read_gyro_dps()`'s Z value. Confirm it's near-zero at rest and changes sign consistently with rotation direction.

**Pass:** `WHO_AM_I` correct; gyro Z responds to rotation with a sign you've now written down (this is the "flip the sign in `main.py` if a by-hand test shows it backwards" check the code's docstring flags).

**If it fails:** I2C address or wiring first (0x68 is assumed in `icm42688.py` — some breakouts strap it to 0x69).

---

## Stage 5 — IR reflectance sensor solo bring-up + `LAP_THRESHOLD` calibration

**Goal:** replace the guessed `LAP_THRESHOLD` with a real number from the actual marker material.

**Setup:** module wired to GPIO26 (ADC0) + power, USB power.

**Procedure:** print raw `ADC(26).read_u16()` continuously while passing the sensor over (a) bare track surface and (b) the actual marker tape/material you intend to use, at the real intended standoff height (§7's fixture geometry, once known). Record both values.

**Pass:** a clear, repeatable gap between the two readings. Set `LAP_THRESHOLD` in `main.py` roughly at the midpoint, with margin on both sides.

**If there's no clear gap:** the marker material/contrast needs to change before this sensor will work reliably — don't paper over it with a marginal threshold.

---

## Stage 6 — Combined electronics bring-up (still on the bench, not on the car)

**Goal:** all three sensors + Pico together, running the real `main.py` fusion loop, before any mechanical integration.

**Setup:** PMW3360 + ICM-42688-P + IR sensor all wired simultaneously per the schematic, USB power (Stage 2's power subsystem can be integrated here too if it's already validated, but isn't required to prove the firmware logic).

**Procedure:** run `main.py` as-is. Since there's no track yet, do a "hand-driven dry run": manually slide and rotate the whole breadboard assembly on a tabletop, roughly simulating a lap (including something crossing the IR sensor's marker test setup from Stage 5 to trigger a lap reset). Watch the printed lap messages and the resulting `track_log.csv`.

**Pass:** `(x, y, θ)` move in directions consistent with how you actually moved the assembly; lap crossings trigger, reset position, and print the expected drift-diagnostic message; the loop doesn't crash or stall; SPI/I2C reads keep succeeding with all three sensors active simultaneously (this is the first point a bus conflict or timing budget problem would show up).

**If it fails:** this is the last stage where a bug is a pure software/wiring problem — everything after this also has mechanical and motor-EMI variables mixed in, which makes the same bug much harder to isolate.

---

## Stage 7 — Mechanical fixture fabrication (parallel-able with Stages 1–6)

**Goal:** a printed, populated front fixture, per `cad/fixture.scad` (`DESIGN.md` §7).

**Gate before printing:** the CAD open items in `DESIGN.md` §8 — real component footprints (from the boards actually used in Stages 3–5, not the typical/placeholder dimensions in the file today) and the real spine cross-section for `rear_splice()`. Printing before these are measured risks a fixture that doesn't fit the parts you've already validated.

**Procedure:** print, dry-fit the sensor boards and Pico without gluing/screwing anything permanent, confirm the standoffs/pockets match the real hardware.

**Pass:** everything physically fits with the clearances `DESIGN.md` flagged as tight (the rotated Pico's ~2mm margin in the 55mm spine section, specifically).

---

## Stage 8 — Full assembly + bench retest

**Goal:** confirm nothing broke moving from breadboard to the soldered/mounted fixture.

**Procedure:** mount and wire everything into the printed fixture per Stage 7, but power it from the bench/USB again first — not the track. Re-run Stage 6's dry-run check in this new physical form.

**Pass:** same as Stage 6. Any regression here is a mounting/wiring/solder-joint problem introduced during assembly, isolated from both the sensor logic (Stage 6 already passed) and the mechanical fit (Stage 7 already passed).

---

## Stage 9 — Off-power on-track fit check

**Goal:** validate the mechanical assumptions that only a real track can test — guide-flag engagement, skid behavior, and sensor standoff over real track surface texture — before adding rail power or the motor to the mix.

**Procedure:** cut the donor chassis (`DESIGN.md` §7) and complete the mechanical splice to the stock rear section, *if not already done as part of Stage 7's fabrication*. With the fixture's electronics still powered from a bench/USB supply (not the rails), place the assembled car in the slot and push it around by hand.

**Check specifically:**
- Guide flag pivots freely, doesn't bind, doesn't pop out of the slot on curves.
- Skid rides smoothly across track-piece seams (the ski-tip geometry from §7 doing its job).
- PMW3360 gets a stable, focused reading over the *real* track surface at the *real* ride height — a lab-desk test in Stage 3 does not substitute for this; track surface texture and lighting are different.
- IR sensor still cleanly detects the marker at the real ride height, not just on a bench jig.

**Pass:** all four hold up over a full hand-pushed lap.

**If the optical sensor doesn't track well here even though Stage 3 passed:** suspect focus height/lens standoff (§7's shim-to-tune note) or track surface reflectivity, not the driver.

---

## Stage 10 — First powered on-track run

**Goal:** rail power and the motor, together, for the first time — this is where motor EMI meeting sensitive SPI/I2C lines becomes a real risk that no earlier stage could test.

**Procedure:** connect to actual rail power via the guide-flag braids (§7's tap point). Low throttle, short run, one or two laps. Watch the serial output live if within cable/WiFi reach, or just let it log and pull the file after.

**Pass:** no SPI/I2C read failures or garbage data correlated with motor activity; supercap ride-through holds up under *real* throttle variation (not the bench-simulated version from Stage 2); a `track_log.csv` comes out with sane-looking numbers.

**If sensor reads glitch specifically when the motor is under load:** that's motor EMI coupling into the SPI/I2C lines — shielding, wire routing away from the motor, or added bypass capacitance near the sensor breakouts are the usual fixes, not a firmware change.

---

## Stage 11 — Full data-collection run + validation

**Goal:** the actual deliverable — a real multi-lap run producing a usable track map, with the lap length reported in metric units.

### How to run a data-collection session

1. **Apply the start/finish tape, across *all* lanes at the same cross-section, not just the one being driven.** A 40mm-wide reflective strip laid across the lane (`DESIGN.md` §6's sizing rule — narrower risks the car passing over it between samples and missing the lap entirely; re-check this width once Stage 5/10 have measured the real loop period and approach speed, per the same section). Pick a spot with a short straight or gentle curve on both sides, not right at the apex of a tight corner — it makes consistent, repeatable positioning of the car easier for the next step, and (mapping more than one lane) means every lane's run starts from the same physical line pointed the same approximate direction, which is what lets their separately-recorded vector paths be combined later (`DESIGN.md` §9).
2. **Place the car on the track roughly 1m before the tape**, sitting in the slot, pointed the right way — a rolling start, so the car is already up to a steady pace by the time it crosses the tape rather than accelerating from a dead stop right on the line.
3. **Power on and wait for gyro calibration to finish.** `main.py` prints `Calibrating gyro bias -- keep the car perfectly still for 1.5s...` and then a result line — the car must not be touched or moved during this window (`DESIGN.md` §6); if the result says `MOVED -- calibration unreliable`, power-cycle and redo this step before proceeding, since a bad calibration here is worse than none.
4. **Drive the car across the tape and continue for 5 complete laps** at a steady pace (`LAPS_TO_RECORD = 6` covers the rolling-start crossing plus 5 timed laps — see `main.py`'s comment on that constant). Multiple laps aren't needed for the gyro calibration itself (that already happened once, at rest, in step 3) — they're what `tools/closed_loop_correct.py --average-out` needs to average down the sensor-noise component of map error that per-lap correction alone doesn't reach (`DESIGN.md` §6). The firmware stops itself automatically after the 6th crossing.
5. **Retrieve `track_log.csv` off the board** before power-cycling it (`mpremote cp :track_log.csv .`, or via Thonny's file browser) — it's the only copy; the Pico's flash isn't otherwise backed up.

### How to post-process the log

6. **Determine `--net-turns` for the real track once** (not per run) by inspecting the driven lane itself: does its own centerline cross itself anywhere, or is it a simple loop? A plain oval, or a lane that merely swaps sides with an *adjacent* lane at a lane-equalizing crossover piece, is `+1.0` (or `-1.0`, depending on direction) — its own path is still a simple loop. Only a lane whose own path genuinely loops back and crosses itself gets a different value (`DESIGN.md` §6 has the full reasoning, and worked this out to `0.0` for the Bolton track's SVG-plan lane used in this project's own simulation — re-derive it for whatever's actually built, since the built track may not match that plan exactly).
7. **Run the closed-loop correction, with averaging:**
   ```
   python3 tools/closed_loop_correct.py track_log.csv --net-turns <value> \
       -o track_log_corrected.csv --average-out track_log_averaged.csv
   ```
   This prints each lap's corrected length in meters, then a summary line like `Lap length: mean 36.349 m over 5 lap(s) (min 36.324, max 36.356, spread 0.032 m)` — **that mean is the measured lap length**, and a small spread relative to the mean is itself a useful sanity check (real, physical measurement noise from an actual run will be larger than this project's simulation shows, so judge it by whether it's small *relative to the track's scale*, not against the simulated figure specifically). Treat `track_log_averaged.csv`'s own length figure as a smoothed map shape for visualization, not a more authoritative length source — see the tool's `--average-out` help text for why.
8. **Plot it:**
   ```
   python3 tools/plot_track_csv.py track_log_corrected.csv
   ```
   Open the resulting `.svg` in a browser.

**Pass:** the plotted shape resembles the actual track layout; the reported lap length is close to the track's known/expected length if there is one to compare against (or at least plausible for its physical size); and the per-lap length spread from step 7 is small relative to the mean. If the spread is large, or the plotted per-lap shapes visibly disagree with each other, heading drift is worse than `DESIGN.md` §2/§6's simulation assumed, and the second-marker heading-correction upgrade mentioned there stops being optional.
