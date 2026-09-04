# Bill of Materials

Parts for **one complete fixture/car** — per `DESIGN.md` §9, mapping every lane of a multi-lane track uses this same physical device driven once per lane, not one device per lane, so this list doesn't scale with lane count.

Status column: **confirmed** = a measured dimension or a part this project has committed to; **TBD** = a generic/illustrative stand-in in the schematic or CAD, still needing a specific part picked (tracked in `DESIGN.md` §8's open items — this file is the shopping list, §8 is why each TBD is still open).

## Electronics

| Qty | Part | Spec / notes | Status | Ref |
|---|---|---|---|---|
| 1 | Raspberry Pi Pico 2 W | RP2350, CYW43439 WiFi | Confirmed | `DESIGN.md` §3, schematic `A1` |
| 1 | PMW3360 optical flow sensor breakout | SPI, needs real SROM firmware sourced separately (`pmw3360.py`'s placeholder) | Confirmed part / firmware TBD | `DESIGN.md` §3, schematic `M1` |
| 1 | ICM-42688-P IMU breakout | I2C, gyro+accel only — no magnetometer variant needed/wanted | Confirmed | `DESIGN.md` §3, schematic `M2` |
| 1 | IR reflectance sensor module | TCRT5000/QRE1113-class, active-IR, analog or digital output to `IR_ADC_PIN` (GPIO26/ADC0) | Confirmed type, specific board TBD | `DESIGN.md` §6, schematic `M3` |
| 1 | Buck-boost regulator module | Input ~0.9–18V → 5V out; "TPS63070-class" is illustrative only | **TBD** | `DESIGN.md` §4, schematic `U1` |
| 1 | Supercapacitor | 1F, 5.5V (schematic value) — re-size once the regulator's real current limit is known (`DESIGN.md` §4) | **TBD** (value provisional) | schematic `C1` |
| 2 | Schottky diode | Small-signal, low-Vf — D1 = reverse-polarity protection on the rail input, D2 = supercap charge-inrush bypass | Confirmed function, specific part TBD | `DESIGN.md` §4, schematic `D1`/`D2` |
| 1 | Resistor, R1 | 4.7Ω provisional — inrush-limiting for the supercap; re-size with the regulator (`DESIGN.md` §4) | **TBD** (value provisional) | schematic `R1` |
| ~0.3m | Hookup wire, small gauge (stranded) | Power tap from the guide-flag braids into `U1`'s input, plus any point-to-point wiring from the breakouts to the Pico's SPI0/I2C0/GPIO pins (`DESIGN.md` §3 pin table) | Confirmed need, gauge/length TBD until layout is final | — |
| 1 | Micro-USB cable | Programming + bench power for the Pico 2 W (keeps the original Pico's connector, not USB-C) | Confirmed | `BRINGUP.md` Stage 0/1 |

## Mechanical

| Qty | Part | Spec / notes | Status | Ref |
|---|---|---|---|---|
| 1 | Donor chassis | Scaleauto Slotcar Chassis 1:24 Analog HS-124 Universal Complete Chassis, plastic, sidewinder, variable wheelbase 96–114mm | Confirmed | `DESIGN.md` §7 |
| 1 | 3D-printed fixture body | From `cad/fixture.scad` — material not yet decided; PLA or PETG are the typical candidates for this fit and load | **TBD** (material) | `DESIGN.md` §7 |
| ~50mm | Rod stock, ~1.2mm diameter | Second (dummy) guide pin — hard plastic (styrene) or brass rod, cut to length, free-pivoting in `rear_guide_mount()` | Confirmed spec, stock source TBD | `DESIGN.md` §7 |
| 2 | Skid pad insert/coating | PTFE tape or a bonded Delrin/POM insert on each of the two ski-tip skid pads (`cad/fixture.scad`'s `skid_pad()`) | **TBD** (material choice) | `DESIGN.md` §7 |
| 4 | M2.5 standoff + screw (or equivalent) | Pico 2 W mounting, matching `pico_hole_d = 2.5mm` in the CAD | Confirmed hole size, hardware TBD | `cad/fixture.scad` |
| — | Splice joint fastener/adhesive (screws or epoxy) | Bridges the cut between the new fixture and the stock rear motor/drive section — `rear_splice()` is still a placeholder lap joint pending the real spine cross-section/rib profile | **TBD** | `DESIGN.md` §7 |

## Consumables

| Qty | Part | Spec / notes | Status | Ref |
|---|---|---|---|---|
| 1 strip | Reflective tape | ~40mm wide (sizing rule, `DESIGN.md` §6), laid across *all* lanes at one cross-section (`DESIGN.md` §9) — enough length to span the full track width plus lane-marker spacing | Confirmed width, brand/material TBD | `DESIGN.md` §6, `BRINGUP.md` Stage 11 |

## Tools (not consumed — bring-up only, `BRINGUP.md` Stage 0)

- Multimeter (essential)
- Breadboard + jumper wires
- Bench-adjustable DC supply (optional — the analog track controller substitutes, since it's already a variable 0–18V DC source)
- Calipers (for the second-guide clearance check, `DESIGN.md` §7, and any future dimension re-checks against real parts)
