# Design Document: Slot Car Track Mapper

Status: concept / pre-implementation. This document captures the reasoning behind the chosen sensing approach and the electrical design, so mechanical/fixture and firmware work can proceed from a shared plan instead of ad hoc experimentation.

## 1. Goal

Reconstruct the 2D shape (path) of a slot car track by carrying a sensor package around the track in a car, without any prior knowledge of the track layout.

## 2. Why optical flow alone is not enough

A single optical-mouse sensor (ADNS-9800, PMW3360, PAW3395, HERO, ...) reports incremental surface displacement **in its own body-fixed axes**, not in world coordinates. A slot car follows the guide slot, so the chassis — and a sensor bolted to it — yaws to track every curve. Through most of a corner the sensor therefore sees close to pure "forward" flow, the same as on a straight. Summing those local (dx, dy) vectors as if they were already in a fixed world frame collapses curves toward straight lines: the sensor isn't wrong, it's just reporting *distance traveled*, not *track curvature*.

To recover the true path you need a heading (yaw) estimate at every sample, so each local displacement can be rotated into world coordinates before it's integrated — standard dead-reckoning. Two ways to get that heading:

1. **IMU fusion (chosen approach).** Add a gyroscope (part of any 6/9-axis IMU) and integrate yaw rate into heading. Rotate each optical (dx, dy) sample by the current heading, then accumulate world-frame position. Single sensor, single extra part, runs entirely as a firmware fusion loop on the Pico.
2. **Dual optical sensors.** Two sensors at a fixed baseline; differencing their along-track readings gives rotation directly (same principle as differential wheel-encoder odometry), no IMU needed. Rejected for v1: doubles SPI wiring and pin budget, and needs precise mechanical spacing on a 1/24-scale fixture.

Mechanical note: ideally the sensor sits directly over the car's guide-pin pivot, since that's the point whose velocity is "pure" body-frame translation. If it's offset by a vector **r** (likely, given fixture constraints), the sensor also picks up a lever-arm term from rotation: `v_sensor = v_pivot + ω × r`. Once ω (from the IMU) and **r** (measured once, fixed) are known this is a straightforward correction in the fusion loop, but **r** needs to be measured accurately when the fixture is built.

The current first-pass CAD layout (§7, `cad/fixture.scad`) places the PMW3360 18mm back from the guide-pin pivot — so `r ≈ 18mm` along the chassis centerline is the current working value for this correction, pending the layout settling down as real part dimensions replace the estimates.

## 3. Selected parts

| Role | Part | Why |
|---|---|---|
| Microcontroller | **Raspberry Pi Pico 2 W** | RP2350: same CYW43439 WiFi as plain Pico W, so `wifimanager.py`'s `network.WLAN` code runs unmodified — chosen over an ESP32 to avoid WiFi-radio scheduling jitter competing with the sensor-fusion polling loop on the same cores. Adds a hardware FPU (Cortex-M33, unlike the RP2040/original Pico's M0+), which directly speeds up the fusion loop's per-sample rotation trig (§6). 520KB SRAM (vs. RP2040's 264KB) gives headroom for the path buffer/logging. Same Pico form factor and largely the same GPIO layout as the original Pico, so `main.py`'s existing pin constants likely carry over without remapping. Considered and rejected: ESP32 (mature MicroPython WiFi, but shares compute with the sensor loop, and requires a full pin remap), Arduino Nano RP2040 Connect (tempting onboard IMU, but its WiFi is a separate NINA module without native MicroPython `network` support — would break `wifimanager.py`). |
| Optical flow sensor | **PMW3360** | Large open-source driver base from mouse-modding/DIY-odometry projects. Performance is comparable to ADNS-9800 and well beyond what slot car speeds need either way. **Correction:** this row originally also claimed "no mandatory SROM firmware upload" as a reason to prefer it over the ADNS-9800 — that's wrong. Every reference PMW3360 driver uploads an SROM firmware blob on power-up via `SROM_Load_Burst`, the same as the ADNS-9800 (see `pmw3360.py`). The SROM step doesn't go away; it just isn't a *worse* bring-up than the ADNS-9800's, so it wasn't actually a differentiator either way. |
| IMU | **ICM-42688-P** | 6-axis gyro+accel with notably lower gyro bias/noise than the ubiquitous MPU6050 — directly reduces the heading-integration drift that's the main source of mapping error in this design (§2). Similar price/I2C-breakout availability to MPU6050. |

The optical sensor and IMU were chosen over alternatives considered (ADNS-9800 kept for reuse, PAW3395 for raw performance, MPU6050 for ubiquity, BNO085 for onboard fusion) mainly on integration risk vs. payoff at this project's actual requirements — see conversation history for the full comparison if reconsidering later.

**Consequence:** `main.py`'s ADNS-9800 SPI register map and `a6_binary.py`'s extracted SROM firmware are now superseded — they'll be replaced by a PMW3360 driver when firmware work starts, not extended. Leave them in place until then as reference for the general SPI-register bring-up pattern (reset → verify product ID → init → poll), which carries over, along with the pin constants (subject to confirming the Pico 2 W's pinout matches).

### Electrical schematic and concrete pin assignments

`electronics/electronics.kicad_sch` is the single-sheet system schematic covering every component above plus the power chain (§4): rail input → reverse-polarity diode → buck-boost regulator → Pico VSYS, with a supercap on the regulated 5V rail and an unmodified tap to the stock motor. The PMW3360, ICM-42688-P, IR reflectance sensor, and the buck-boost regulator don't have real breakout-specific KiCad symbols, so they're drawn as generic pin-header connectors labeled by net — see the file's own text notes for what's a real part symbol (Pico 2 W, using the pin-compatible RP2040 `RaspberryPi_Pico` library symbol) versus a documentation stand-in. Passes ERC clean (0 violations) with explicit no-connect flags on every intentionally-unused pin.

Drawing it forced concrete GPIO assignments, which now supersede the vague "SPI0"/"I2C0" labels used earlier in this document:

| Signal | Pico 2 W pin |
|---|---|
| SPI0 SCK / MOSI / MISO / CS → PMW3360 | GPIO10 / GPIO11 / GPIO12 / GPIO13 |
| PMW3360 MOTION (interrupt) | GPIO14 |
| I2C0 SDA / SCL → ICM-42688-P | GPIO4 / GPIO5 |
| ICM-42688-P interrupt | GPIO6 |
| IR reflectance sensor output | GPIO26 (ADC0) |

The SPI pins land on the exact same GPIOs `main.py` already uses for the ADNS-9800 (`SPI_CLK=10, MOSI=11, MISO=12, CS=13`) — but GPIO14, previously the ADNS-9800's `RESET_PIN`, is repurposed as the PMW3360's motion-interrupt input (the PMW3360 has no reset pin). That's a change in *meaning*, not just reuse — flag it clearly when the firmware is rewritten so it isn't mistaken for a leftover reset line.

Per §2's environmental note: configure the ICM-42688-P (or any future IMU swap) for gyro+accel only — no magnetometer is on this part, so the mag-interference risk from the motor magnets doesn't apply here, which is one more point in its favor over 9-axis parts.

## 4. Power: analog controllers change the constraint

Confirmed: controllers are analog (resistive/linear throttle), not PWM. That means rail voltage is a clean, un-chopped DC level — but one that is *intentionally* proportional to trigger position, from ~0 V (stopped) up to full pack voltage (typically 12–18 V) at full throttle. This is a harder power problem than a PWM system, not an easier one: there is no fixed high-frequency carrier to hold electronics up between pulses, because at low throttle there may genuinely be almost no rail voltage at all.

Implications:

- A simple buck regulator won't work across the whole range — it can't produce 3.3/5 V once the input sags below its dropout, which will happen exactly when the car is slow or stopped.
- A **buck-boost** regulator (e.g. TI TPS63070-class, ~0.9–18 V in) extends the usable range down much further, but still has a floor near true 0 V.
- Below that floor, only stored energy keeps the electronics alive.
- Cheap first check worth doing before building anything: some analog 4-rail track systems carry a separate constant-voltage accessory/lighting supply (for car headlights) independent of the throttle rail. If this track has one, tapping it sidesteps the whole problem.
- Include basic input protection (reverse-polarity diode / small TVS) regardless of source — pickup shoes can momentarily bridge or reverse polarity on crashes/spin-outs.

### Energy buffer: supercapacitor (selected)

**Decision: a single supercapacitor, not a LiPo battery**, sized to ride through brief low-throttle/contact-loss moments during an active mapping lap — not to keep the device alive for extended parked periods, which isn't this project's requirement. Reasoning:

- **Simplicity:** a supercap needs no charge-management *IC*, no protection circuit, and no power-path chip — at most a resistor and a diode (below), not a dedicated chip. A LiPo needs all three (charger IC, protected cell, ideally a power-path chip to avoid a hard switchover between rail power and battery power) for a small cost/weight saving that doesn't matter here.
- **Crash safety:** slot cars hit barriers. A punctured/crushed LiPo pouch is a real fire risk; a damaged supercap is not. This matters more here than in most projects.
- **Fit to duty cycle:** supercaps self-discharge faster than LiPo and don't hold charge for long-term storage — irrelevant for a device that's only ever active while running on the track, where it's continuously recharged during every high-throttle segment.

**Placement — regulator output, not regulator input:** don't connect the supercap directly across the raw rail; the rail swings up to full pack voltage (12–18 V), well above a single 5.5 V-rated cell, and multi-cell series stacks need balancing (reintroducing the complexity being avoided). Instead:

```
rail → [buck-boost regulator] → 3.3V/5V logic rail → Pico/sensors
                                        |
                                  [R1] (charge current limit)
                                   |       |
                                  [D2] ---‖ (bypasses R1 when the cap is
                                   |          discharging — ride-through
                              [supercap]     current isn't limited by R1)
```

Size the cap with `C = I × t / ΔV`: at a rough 80–100 mA logic load, accepting the rail sagging from 3.3 V to ~2.7 V before it's risky, a 1 F/5.5 V cell (~$1–2) buys a few seconds of full ride-through with zero rail voltage; a 10 F/5.5 V cell (~$2–5) buys tens of seconds.

**Charging isn't free, though, and it isn't just "the regulator's current limit handles it."** Connecting a fully-discharged cap directly to a live regulator output looks like a near dead-short for the first instant — worth limiting explicitly rather than trusting an unspecified regulator's behavior. `electronics/electronics.kicad_sch` adds:

- **R1** (provisionally 4.7Ω) in series between the regulated rail and the cap, limiting charge inrush.
- **D2** (Schottky) in parallel with R1, oriented so the cap can *discharge* back into the rail through D2's low forward drop instead of through R1 — otherwise R1 would eat into the very ride-through voltage margin the cap exists to provide.

This means charge time is now an `R1 × C1` problem, not just a regulator-current problem — and it cuts the other way from the ride-through sizing above: `t_charge ≈ 5 × R1 × C1` (5 time constants ≈ full charge). With R1 = 4.7Ω: a **1F cap charges in ~24s**; a **10F cap would take ~4 minutes** — long enough that the device wouldn't have its ride-through protection for the first few minutes of every session. **This pushes the practical choice toward the 1F end of the range above, not the 10F end**, unless R1 is reduced (which weakens inrush protection) — the two were sized independently earlier in this doc and need to be sized together. Revisit both once a real regulator's current limit is known (its datasheet may make R1 unnecessary or let it shrink).

**Reconsider LiPo only if** the requirement changes to "must stay powered for minutes with no rail contact" (e.g. logging while parked in the pits) — a supercap can't do that in a small/cheap package. If that happens: single protected 1S cell (100–150 mAh) + a linear charger IC (MCP73831-class) + ideally a power-path chip (BQ24075-class) to charge and run simultaneously without switchover glitches. Budget for ongoing battery-health concerns then too (over-discharge cutoff, cycle-life fade, no long-term full/empty storage).

See `electronics/electronics.kicad_sch` for the R1/D2/C1 sub-circuit as drawn (ERC-clean).

## 5. System block diagram (IMU fusion option)

```
                    TRACK RAILS (analog DC, ~0-18V, varies with throttle)
                              |                    |
                              v                    v
                   +---------------------------------------+
                   |     Pickup shoes / contact braids      |
                   +---------------------------------------+
                              |                    |
                              v                    v
        +----------------------------------------------------------+
        |          reverse-polarity protection (diode/TVS)          |
        |          buck-boost regulator, Vin ~0.9-18V -> 3.3V/5V    |
        +----------------------------------------------------------+
                              |
                              v  regulated 3.3V/5V rail
                              +---------------------------+
                              |  supercap (5.5V-rated),    |
                              |  rides out low-throttle /  |
                              |  contact-loss dips         |
                              +---------------------------+
                              |
        +----------------------------------------------------------+
        |               Raspberry Pi Pico 2 W (RP2350)               |
        |                                                            |
        |  SPI0 (CLK/MOSI/MISO/CS, RESET) -------------------------->|---> Optical flow sensor
        |                                                            |     (PMW3360) mounted over
        |                                                            |     track surface, at/near
        |                                                            |     guide-pin pivot
        |                                                            |
        |  I2C0 (SDA/SCL) ------------------------------------------>|---> IMU (ICM-42688-P,
        |                                                            |     gyro + accel), rigidly
        |                                                            |     mounted, axes aligned to
        |                                                            |     chassis forward/lateral/
        |                                                            |     vertical
        |                                                            |
        |  GPIO/ADC ------------------------------------------------>|---> IR reflectance sensor
        |                                                            |     (TCRT5000/QRE1113),
        |                                                            |     mounted alongside PMW3360,
        |                                                            |     reads start/finish marker
        |                                                            |
        |  [optional] SPI1/SD -------------------------------------->|---> onboard logging (SD/flash)
        |  [optional] onboard WiFi (wifimanager.py) ----------------->|---> base station / laptop
        +----------------------------------------------------------+
```

## 6. Firmware fusion loop

Implemented in `main.py` (with `pmw3360.py` and `icm42688.py` as the sensor drivers) — not yet tested on real hardware, see those files' own caveats. Per sample tick:

1. Read gyro yaw rate from IMU; integrate into heading `θ`.
2. Read (dx, dy) from optical sensor (body frame); apply the lever-arm correction `v_pivot = v_sensor − ω × r` using this tick's rotation and the measured mounting offset **r** = 18mm (CAD, §2, §7).
3. Rotate the corrected (dx, dy) by `θ` into world coordinates; accumulate into running position (X, Y).
4. Write (t, X, Y, θ, lap) as a CSV row to flash on every tick, flushed every 50 samples — chosen over "buffer everything, write once at the end" specifically because this project's own power story (§4) means a mid-run brownout is a real, not theoretical, risk; buffering it all in RAM would lose an entire run to a single dropout.
5. On lap-trigger detection (below), reset accumulated position to (0, 0) — the marker's own location, since that's what defines the origin; heading `θ` is left as-is (the trigger carries no direction information — see below).

Calibration this first pass still needs (not yet possible without hardware in hand): the real PMW3360 SROM firmware (`pmw3360.py` has a zeroed placeholder — see §3's correction), `LAP_THRESHOLD` tuned against the real IR marker's light/dark ADC values, and a by-hand sanity check that the gyro sign and the optical sensor's dx/dy axes match the code's assumed convention (documented at the top of `main.py`) — get any of those three wrong and the map will be systematically distorted in a way that's easy to misattribute to the physics instead.

### Gyro-bias calibration (at power-up)

**Implemented in `main.py` as `calibrate_gyro_bias()`, run once at startup before the fusion loop begins.** `sim/simulate_track_run.py` (built to generate expected sensor data for the real Bolton club track, §6/§8) modeled a deliberately modest, realistic 0.3°/s uncalibrated gyro bias and found it responsible for roughly **320mm of reconstructed-position error by the end of a single 12.5s lap** (isolated by re-running the simulation's own closing-error check with the bias zeroed: ~1080mm with the bias present vs. ~750mm without it) — comparable to, and in the same direction as, the optical sensor's own noise contribution. *Correction: an earlier version of this section attributed the entire ~1.1m closing error to gyro bias alone; isolation testing during implementation showed the remaining ~750mm is a baseline artifact of the simulation script's own heading-synthesis method (see `HEADING_WINDOW_MM`'s caveat comment in `sim/simulate_track_run.py`), not something attributable to gyro bias, noise, or a defect in the fusion algorithm itself — flagged in case a future pass re-derives these numbers and gets a different split.* Either way, the lap-reset (below) hides the bias's within-lap effect by zeroing (X, Y) at each marker crossing, but it does nothing for heading, which keeps accumulating the same bias lap after lap; any use of the map beyond "one lap's shape" (comparing laps, averaging them, trusting absolute heading) needs this fixed at the source.

**Design (as implemented):**

1. **Before the run starts, with the car held stationary** (on the bench or sitting still in the slot), sample the gyro Z axis for a short fixed window (`GYRO_CAL_DURATION_MS`, 1.5s) and average the readings to estimate the static bias `gz_bias`.
2. **Subtract `gz_bias` from every raw gyro reading** before integrating it into heading, for the remainder of that run. This runs fresh at the start of every `run()` call rather than storing a calibration constant across runs/power cycles — gyro bias drifts with temperature and time, so yesterday's measured bias is not a safe stand-in for today's.
3. **Verify stillness during the calibration window** using the accelerometer already being read for other purposes (§3/§6) — `calibrate_gyro_bias()` checks its combined variance over the window against `GYRO_CAL_MAX_ACCEL_STD_G` and prints a `MOVED -- calibration unreliable` warning rather than silently baking a bad bias into the whole run (it doesn't yet block/retry the run automatically — that's a possible follow-up once real accelerometer noise floor data says what threshold is actually reliable).
4. **Limitation, by design:** this corrects the *static* bias present at power-up, not in-run bias wander — it's a start-of-run correction, not a continuous one. A zero-velocity update (detecting known-stationary moments during a run, e.g. the car briefly stopped) would address in-run wander if it turns out to matter — not needed for v1, noted here so it isn't forgotten if lap-to-lap heading error looks worse than this calibration alone can explain.

### Lap-detection mechanism (selected)

**Decision: onboard active-IR reflectance sensor (e.g. TCRT5000/QRE1113-class) reading a physical contrast marker (tape strip) laid across the track at the start/finish line.** Mounted on the car alongside the PMW3360, near the guide-pin pivot — the guide pin tightly constrains lateral position, so the sensor sweeps the same physical point on the marker every lap with no alignment tolerance needed.

Rejected alternatives and why:
- **Software-only ("near starting X,Y after N seconds")** — circular: uses the very dead-reckoned position that's drifting to decide when to correct it. Breaks outright on a self-crossing layout (figure-8), where "near start" is ambiguous.
- **Hall sensor + embedded magnet** — the motor's own permanent magnets sit right next to the mounting location; a simple threshold Hall switch can't reliably separate "external track magnet passing underneath" from "background field from my own motor." Same interference family already ruled out for magnetometer fusion (§3).
- **Mechanical lever/bump strip** — physical obstruction on the track, wear over many laps, risk of inconsistent engagement (bounce/skip).
- **External trackside IR gate** — moves the sensor off the car, but the correction has to be applied *onboard* where the dead-reckoning state lives, so it still needs a real-time wireless link back to the car, plus trackside alignment every time the layout is reconfigured. More moving parts than a sticker.

Active-IR reflectance (emits and reads its own reflected IR) is immune to ambient lighting, unlike a bare phototransistor, and the module is sub-$1 with a simple GPIO/ADC read.

**Limitation:** a single marker crossing gives a position reference only, not heading — heading keeps relying on the ICM-42688-P's gyro integration between corrections. If heading drift becomes visible over many laps, a second marker a short known distance downstream would let the time-of-flight between the two triggers derive an instantaneous heading correction too — a future upgrade, not needed for v1.

**Debounce:** ignore any trigger occurring less than some fraction of the expected lap time since the last one, so a wide/uneven marker edge or a bounce doesn't double-fire the correction.

**Tape width — size it to the sampling, not just to "wide enough to see":** `main.py`'s loop is unthrottled (no `sleep()`), so its real sample period is whatever SPI+I2C+math+logging overhead works out to on real hardware — not yet measured (§8). `sim/simulate_track_run.py`, at its 100Hz assumption and ~3 m/s tape-crossing speed, showed only **1 sample** landing above `LAP_THRESHOLD` with a 12mm tape — a single missed sample (loop jitter, a slightly faster pass) means a missed lap entirely.

The sizing rule: for a loop sampling at period `T` and a car crossing at speed `v`, any tape narrower than `v·T` (in the direction of travel) can fall entirely between two samples and be missed outright; `2·v·T` guarantees at least one sample with some margin either side of exact alignment. E.g. at `v`=3–6 m/s and an assumed `T`=10ms (100Hz, itself unverified — see above): 30–60mm for a bare guarantee, 60–120mm for margin.

**Recommendation: start with a 40mm-wide tape strip** (re-confirmed against `sim/simulate_track_run.py`, which now catches 2 samples at its simulated pace with this width) as a practical starting point, and revisit against the *measured* loop period once real hardware timing is in hand (§8) — narrower is fine if the real loop turns out faster than 100Hz, wider is needed if slower. Driving a controlled, less-than-flat-out pace specifically across the line (lower `v` at the crossing) directly buys the same margin as a wider tape, per the same formula, and costs nothing to try first.

## 7. Fixture: donor chassis conversion

**Donor:** Scaleauto HS-124 Universal Complete Chassis (plastic, sidewinder, variable wheelbase 96–114mm). Measured on the chassis in hand: wheelbase 114.25mm, rear track width (outside-to-outside) 80.72mm, front track width (outside-to-outside) 77.83mm, main chassis spine width 55mm, V score-line to (former) front axle centerline 47mm, front axle centerline to guide-flag tip 18mm, spine plastic thickness at the cut face 3.6mm, guide-flag pivot peg 3.8mm diameter × 7mm engagement depth. Sidewinder layout: motor mounted along the chassis's long axis driving the rear axle through a pinion/spur gear pair; guide flag at the front doubles as the mechanical slot-engagement piece *and* the power pickup (its braids feed two wires running the full chassis length back to the motor terminals).

**The caliper measurements matter beyond just accuracy:** the replaceable front section is only 65mm long (47+18mm) — barely half of the ~112mm first guessed from photos. That's tight enough to change the layout, not just tune it: the Pico 2 W's 51mm length alone would eat most of the available space if mounted the "normal" way (long axis along the direction of travel), so `cad/fixture.scad` now mounts it rotated 90° — long axis running across the fixture's width — trading length for width, which the flared deck has to spare. See the CAD subsection below.

**Plan:** cut the chassis at its molded score line ("the V") in front of the motor box. Keep the rear section (motor + driven axle/wheels) stock and unmodified — propulsion is untouched. Replace the front section with a custom-fabricated fixture carrying the Pico 2 W, PMW3360, ICM-42688-P, and IR reflectance lap sensor (§3, §6), plus the guide flag.

Requirements this imposes on the fixture, beyond sensor mounting:

- **Preserve the guide flag's pivot mount.** It self-centers in the slot on a small pivot peg in the stock chassis; that compliance is part of how the car tracks corners. Rigidly fixing it instead of carrying the pivot over risks poor cornering or the flag popping out of the slot.
- **Reuse the guide flag's pickup braids as the rail power tap.** They're already the existing power path into the car — splice the buck-boost regulator's input into the same two wires (or a shared node) feeding the motor, rather than adding a separate tap. Cutting the chassis severs the existing wire run regardless, so this re-routing has to happen either way.
- **Bridge the cut structurally, not just electrically.** Removing the scored section removes the plastic that transmitted chassis stiffness between front and rear — the fixture needs to mechanically splice the two halves back into one rigid chassis, not just sit alongside the rear section.

**Front support: sled/skid (selected over small idler wheels).** The stock front wheels are non-driven idlers to begin with (the slot does the steering), so removing them is low-risk, and skid/floating front ends are already a precedented technique in the hobby (e.g. F1-style slot chassis). The decisive reason for this project specifically: a skid lets the optical sensor's standoff height be referenced directly off the same molded contact surface that sets ride height, rather than being at the mercy of separate bearing/axle/suspension play — one less independent source of variance in the one dimension (sensor-to-track distance) this whole design most needs to hold constant.

Design constraints that follow from choosing a skid:

- **Two contact points (or one wide skid), not a single central point**, spaced at roughly the stock front track width (77.83mm outside-to-outside) — a single-point skid can rock side-to-side, and that rocking would inject false roll into both the optical flow reading and the IMU.
- **Rounded/ski-tip leading edge**, not a flat/sharp one — track-piece seams are exactly where small height discontinuities occur, and a flat skid edge is more likely to catch on a proud seam than a rounded one is to bridge it.
- **Low-friction, wear-resistant skid material** (e.g. PTFE tape or a bonded Delrin/POM insert) — sliding friction is higher than rolling friction, and unlike a wheel, a worn skid directly lowers ride height (and therefore sensor focus distance) over time.
- **Reference the sensor mount to the skid, not to an independent chassis datum** — mount the PMW3360's standoff at a fixed distance from the skid's own contact plane on the same molded part, so the two stay coupled even if the skid wears.

**Open risk to validate once a prototype exists (not blocking the design, just untested):** sliding stick-slip friction can produce higher-frequency vibration than a rolling contact would, which could show up as noise in the optical flow and accelerometer readings. If that turns out to be a real problem in practice, the mitigation is a material/geometry change to the skid tip, not a redesign of the fusion approach.

### CAD model

`cad/fixture.scad` is the parametric OpenSCAD model implementing this section: rear splice tab, a deck that flares from the 55mm spine width out to the 77.83mm front track width (so the skids actually land on structure instead of floating past a narrow deck's edge), Pico 2 W + ICM-42688-P mounted on top, PMW3360 + IR reflectance sensor hanging below near the guide-flag pivot, and the two ski-tip skid pads. All donor-chassis dimensions in the file are now from calipers (this section's opening paragraph); the component footprints (Pico/PMW3360/ICM-42688-P/IR module exact sizes) are still typical/placeholder values pending the actual parts bought, and `rear_splice()` is still a placeholder lap joint pending the real spine cross-section/rib profile — not print-ready on either count yet.

Render previews with e.g. `openscad --autocenter --viewall -o preview.png cad/fixture.scad`; the file's `echo()` statements print the computed total length, the resulting lever-arm `r` (§2), and flag if a sensor standoff or the Pico's mounting zone comes out negative/too tight.

## 8. Open items before build

- Confirm whether this track has a constant-voltage accessory rail (would simplify §4 significantly).
- Measure/fix the sensor-to-pivot offset **r** once the fixture is machined.
- Apply the start/finish marker to the track and record its true (X₀, Y₀) as the mapping origin. Start with a 40mm-wide tape strip (§6's sizing rule) and re-check it once the real loop period and approach speed are measured.
- Measure `main.py`'s actual achieved loop period on real hardware (it's unthrottled — no `sleep()` — so this is currently unknown, not just uncalibrated) and re-run §6's tape-width sizing formula against the real number.
- Measure real logic-rail current draw on the built fixture and size the supercap (§4) from it rather than the rough estimate.
- Source PMW3360, ICM-42688-P, IR reflectance sensor, Pico 2 W, and buck-boost regulator/supercap parts and confirm they all physically fit the 1/24 fixture footprint.
- Confirm the real Pico 2 W board's GPIO pin numbering matches the RP2040 `RaspberryPi_Pico` library symbol used in the schematic (§3 addendum) and now hard-coded in `main.py`.
- Source the real PMW3360 SROM firmware and replace `pmw3360.py`'s placeholder (§3's correction, §6) — nothing optical will work correctly until this is done.
- Run `main.py` on real hardware for the first time and work through its documented calibration steps: `LAP_THRESHOLD` against the actual IR marker, the gyro-sign/optical-axis sanity checks, and confirm `calibrate_gyro_bias()`'s stillness threshold (`GYRO_CAL_MAX_ACCEL_STD_G`) against the real accelerometer's noise floor (§6).
- Calibrate the PMW3360's actual CPI-to-distance conversion by rolling a known distance, rather than trusting the nominal CPI setting in `pmw3360.py`.
- Get the actual PMW3360, ICM-42688-P, and IR reflectance breakout boards and replace `cad/fixture.scad`'s typical/placeholder footprint dimensions with real ones (donor-chassis dimensions are now measured — this is the remaining unverified category).
- Redesign `rear_splice()` in the CAD model as a real tongue-and-groove or screwed lap joint once the stock spine stub's cross-section (thickness, ribs) is measured — 3.6mm is the flat thickness at the cut face, not the full joint profile.
- Double-check the Pico 2 W's real board+header footprint (not just the bare PCB outline) against the ~2mm per-side clearance the rotated mount currently has in the 55mm-wide spine section — tight enough to matter.
- Prototype the skid and check for stick-slip vibration in practice (§7's open risk) before committing to a final skid material/geometry.
- Print/fabricate the front fixture from the finalized CAD model.
- Design the mechanical splice + wiring re-route across the cut (§7) between the new front fixture and the stock rear motor/drive section.
- Pick an actual buck-boost regulator part (§4 says "TPS63070-class" illustratively; `electronics/electronics.kicad_sch` represents it as a generic labeled connector) and, once chosen, swap in its real symbol/footprint.
- Re-size R1 and C1 together once that regulator's real current limit is known (§4) — R1=4.7Ω/C1=1F is provisional, picked before either the regulator or the cap was final.
- Same for the PMW3360/ICM-42688-P/IR reflectance breakout boards in the schematic — generic connectors for now, real symbols once specific boards are bought (tie this to the CAD footprint task above).
