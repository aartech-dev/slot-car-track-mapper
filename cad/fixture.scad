// ======================================================================
// Slot Car Track Mapper — Front Sensor Fixture (parametric, first pass)
//
// Donor chassis: Scaleauto HS-124, plastic, sidewinder, variable
// wheelbase 96-114mm. See ../DESIGN.md §7 for the full mechanical plan
// and reasoning behind every decision referenced below.
//
// Cut the donor chassis at its molded score line ("the V") in front of
// the motor box. The rear motor/drive section is kept stock and is NOT
// modeled here. This part REPLACES the front section: it splices onto
// the rear stub, carries the guide flag, the Pico 2 W, the PMW3360, the
// ICM-42688-P, and the IR reflectance lap sensor, and rides on a
// two-point skid instead of the stock front wheels.
//
// Units: mm. X=0 at the rear cut face, +X toward the front/guide flag.
// Y=0 on the car's centerline. Z=0 at the track surface.
//
// ---------------------------------------------------------------------
// STATUS: third pass. All donor-chassis dimensions below are now from
// calipers on the real part (not photo estimates), including the
// front-of-motor carrier profile (tmp/chassis-front-of-motor.jpeg) that
// the fixture's rear edge now mirrors — see carrier_interface() below,
// which replaces the old flat-cube rear_splice() placeholder. The second
// (rear) guide pin no longer has fixture-side geometry: it uses a small
// pre-existing hole near the carrier's tab tip instead of a molded boss.
// Still NOT print-ready: the component footprints (Pico/PMW3360/
// ICM-42688-P/IR module) are still typical/placeholder values — verify
// those against the actual parts bought before printing.
// ======================================================================

// ---- MEASURED on the physical chassis (trust these) -------------------
wheelbase           = 114.25;
front_track_width   = 77.83;  // outside-to-outside, stock front wheels
rear_track_width    = 80.72;  // outside-to-outside, stock rear wheels (kept stock — informational only)
spine_width         = 55.0;   // width of the main chassis spine at the cut
cut_to_front_axle   = 47.0;   // OLD flat-cut estimate to the (former) front axle centerline —
                               // superseded by the carrier_* profile below now that the mating edge
                               // follows the motor carrier's contour instead of a straight cut; kept
                               // for reference only, no longer feeds total_length (see below).
front_axle_to_guide = 18.0;   // front axle centerline to guide-flag tip
spine_thickness     = 3.6;    // stock spine plastic thickness at the cut face
guide_peg_dia       = 3.8;    // stock guide-flag pivot peg diameter
guide_peg_depth     = 7.0;    // stock guide-flag pivot peg engagement depth

// ---- MEASURED: front-of-motor carrier profile (tmp/chassis-front-of-motor.jpeg) ----
// The kept rear section's front face isn't a flat cut — it's this raised
// (carrier_h tall) wedge-and-tab boss molded into the chassis, sitting in
// front of the motor box. The fixture doesn't butt a flat face against a
// flat cut; its leading edge is notched to MIRROR this exact outline so
// the two halves key together and self-align. There's also a small
// pre-existing hole near the tab tip that the second (rear) guide pin
// uses directly — no fixture-side boss needed for it, unlike the earlier
// design's rear_guide_mount() (removed).
carrier_base_w      = 41.45;  // width at the base (widest point, nearest the motor)
carrier_base_len    = 7;      // length of the two parallel sides before the taper starts
carrier_taper_len   = 28.5;   // length of the two tapering sides, base width down to the tab width
carrier_tab_w       = 6.25;   // tab width
carrier_tab_len     = 10;     // tab length, taper apex to the top of the radiused tab tip
carrier_h           = 3.5;    // height of the carrier boss above the surrounding chassis floor —
                               // also the fixture's thickness at the mating edge, so both faces meet flush
carrier_total_len   = carrier_base_len + carrier_taper_len + carrier_tab_len;  // 45.5mm, base to tab tip
carrier_clearance   = 0.3;    // per-side clearance so the notch actually seats over the real part
carrier_wall        = 2;      // solid plastic left beyond the tab tip, for edge strength
carrier_zone_len    = carrier_total_len + carrier_wall;  // 47.5mm — how far forward the interface plate extends

total_length = carrier_zone_len + 55;
// NOTE: total_length used to be cut_to_front_axle + front_axle_to_guide (65mm) with a 10mm placeholder
// splice (rear_splice()). Now that the rear interface is the real carrier_zone_len (47.5mm) instead of
// that 10mm placeholder, the fixture is elongated by the same amount (+37.5mm) so the Pico/sensor/
// guide-flag zone ahead of it keeps the same 55mm of usable length it had before.

// Lever arm from the guide-pin pivot (DESIGN.md §2) to wherever the
// optical sensor actually ends up — feed this into the fusion loop's
// lever-arm correction once it's finalized here.
pmw_x = total_length - front_axle_to_guide;
lever_arm_r = total_length - pmw_x;

// ---- Component footprints — VERIFY against the specific parts bought --
pico_l = 51; pico_w = 21;                                  // Pico 2 W board outline
pico_hole_dx = 47; pico_hole_dy = 17; pico_hole_d = 2.5;    // mount-hole pattern (+ clearance)

// PMW3360DM-T2QU + LM19-LSI lens — MEASURED from the real datasheet
// (tmp/C20612443.pdf, PMW3360 Product Datasheet Rev 1.50), not typical
// guesses. Fig. 4 ("Assembly drawing... distance from lens reference
// plane to tracking surface") and Fig. 8 ("Recommended Base Plate
// Opening") describe exactly the joint our deck needs to form — the
// datasheet's "Base Plate" IS our fixture deck.
pmw_l = 19.00; pmw_w = 21.35;               // Fig. 8 recommended base-plate opening keepout (X/Y — axis
                                              // assignment is a reasonable-not-yet-verified read of the
                                              // drawing; both fit comfortably in our available space either way)
pmw_opening_r    = 7.05;                     // Fig. 8 outer opening corner radius
pmw_hole_w       = 10.97; pmw_hole_l = 10.97; // Fig. 8 Detail F inner pass-through hole (approximated as a
                                              // rounded square — the real opening is a "D" shape with a
                                              // 69.6° taper wall; refine once the lens is in hand)
pmw_hole_r       = 2.00;                     // Fig. 8 Detail F inner hole max corner radius
pmw_base_plate_t = 2.40;                     // Fig. 8 recommended base-plate thickness at the opening —
                                              // the deck must be thinned to exactly this locally, not deck_t,
                                              // or the lens flange sits proud and focus distance grows
pmw_focus_height = 2.40;                     // Fig. 4 "Bottom of Lens Flange to Navigation Surface (Z)" —
                                              // confirms the old "typical" 2.4mm guess was exactly right
pmw_pcb_standoff = 2.90;                     // Fig. 4 "Gap between PCB & Base Plate" — the sensor PCB (with
                                              // the lens clipped to its underside, Fig. 5) mounts this far
                                              // ABOVE the deck's top surface, not hanging below it
pmw_pcb_t        = 1.60;                     // Fig. 4 PCB thickness

icm_l = 15; icm_w = 15; icm_t = 3;                         // ICM-42688-P breakout, typical

ir_l = 32; ir_w = 10; ir_module_h = 5;                     // TCRT5000-style reflectance module, typical
ir_focus_height = 3.0;                                      // typical optimal sensing distance — verify vs. datasheet

// ---- Fixture structural parameters -------------------------------------
deck_t    = 3;    // main deck thickness
skid_h    = 9;    // ground clearance: track surface to underside of deck
skid_w    = 6;    // each skid pad's width (Y)
skid_len  = 14;   // each skid pad's length (X) — shrunk to fit the real (shorter) total_length
ski_tip_r = 3;    // radius rounding the skid's leading edge, so it bridges track-piece seams

standoff_ir  = skid_h - ir_focus_height  - ir_module_h;
pmw_pocket_depth = deck_t - pmw_base_plate_t;  // how much the outer counterbore must remove from the
                                                // deck's top face so pmw_base_plate_t of material remains

echo(str("total_length = ", total_length, " mm"));
echo(str("lever_arm_r (guide pivot to PMW3360) = ", lever_arm_r, " mm"));
echo(str("pmw lens pocket: deck_t ", deck_t, "mm - base_plate_t ", pmw_base_plate_t, "mm = ", pmw_pocket_depth,
    "mm counterbore depth ", pmw_pocket_depth < 0 ? "*** NEGATIVE — deck_t must be >= pmw_base_plate_t ***" : "(OK)"));
echo(str("ir standoff spacer needed = ", standoff_ir, " mm ", standoff_ir < 0 ? "*** NEGATIVE — increase skid_h or use a thinner module ***" : "(OK)"));

$fn = 48;

flare_start = carrier_zone_len + 32;  // X where the deck begins widening from the spine to the skid
                                       // track width — carries forward the same 32mm gap the original
                                       // (10mm-splice) design used between its splice and flare_start
deck_front  = total_length - 2;       // X of the deck's front edge, almost at the guide-flag tip

echo(str("carrier interface: base ", carrier_base_w, "mm -> tab ", carrier_tab_w,
    "mm over ", carrier_total_len, "mm, ", carrier_h, "mm tall, ", carrier_clearance, "mm/side clearance"));
echo(str("usable length between the carrier interface and the flare (Pico zone) = ",
    flare_start - carrier_zone_len, " mm — Pico 2 W needs at least its short-axis dimension here since it's mounted rotated"));

// Second (rear) guide pin, DESIGN.md §7: no longer fixture geometry — it
// uses a small pre-existing hole near the motor carrier's tab tip (kept
// rear section), bracketing the PMW3360 between it and the front guide
// (guide_flag_mount(), below) without needing a molded boss here. Measure
// that hole's exact position once accessible and re-run the DESIGN.md §7
// chord/arc-mismatch check (r_worst_mm = 221.1mm, the tightest lane) using
// its real spacing from front_guide_x = deck_front - 1.

module deck() {
    // Constant-width rear section at the spine width (mates with the
    // carrier_interface()), then flares out to front_track_width so the skids
    // (placed at the stock front track width for roll stability, DESIGN.md
    // §7) actually land on structure instead of floating past the edge of
    // a 55mm-wide deck — the same reason the stock chassis needs separate
    // lateral arms to reach its wheels from the narrow spine.
    translate([carrier_zone_len, -spine_width/2, skid_h])
        cube([flare_start - carrier_zone_len, spine_width, deck_t]);
    hull() {
        translate([flare_start, -spine_width/2, skid_h])
            cube([0.1, spine_width, deck_t]);
        translate([deck_front, -front_track_width/2, skid_h])
            cube([0.1, front_track_width, deck_t]);
    }
}

module carrier_profile_2d() {
    // The motor carrier's wedge-and-tab outline, base (widest, nearest the
    // motor) at X=0, tab tip (narrowest, radiused) at X=carrier_total_len.
    // Built as a union of hulls so each segment (base rect / taper
    // trapezoid / rounded tab) is an exact straight-sided or circular
    // boundary, not a polygon approximation.
    x_base_end  = carrier_base_len;
    x_taper_end = carrier_base_len + carrier_taper_len;
    x_tip_c     = x_taper_end + carrier_tab_len - carrier_tab_w/2;

    union() {
        hull() {
            translate([0, -carrier_base_w/2]) square([0.01, carrier_base_w]);
            translate([x_base_end, -carrier_base_w/2]) square([0.01, carrier_base_w]);
        }
        hull() {
            translate([x_base_end, -carrier_base_w/2]) square([0.01, carrier_base_w]);
            translate([x_taper_end, -carrier_tab_w/2]) square([0.01, carrier_tab_w]);
        }
        hull() {
            translate([x_taper_end, -carrier_tab_w/2]) square([0.01, carrier_tab_w]);
            translate([x_tip_c, 0]) circle(d = carrier_tab_w);
        }
    }
}

module carrier_interface() {
    // Flush butt-joint region: carrier_h thick (matching the carrier
    // boss's height, so the two faces meet flush, per the user's
    // measurement) with a notch mirroring carrier_profile_2d() (grown by
    // carrier_clearance so the real part actually seats in it) cut into
    // its leading edge. This is the "socket" — replaces the old flat-cube
    // rear_splice() placeholder now that the real motor-carrier contour
    // (tmp/chassis-front-of-motor.jpeg) is known.
    translate([0, 0, skid_h])
        linear_extrude(carrier_h)
            difference() {
                translate([0, -spine_width/2])
                    square([carrier_zone_len, spine_width]);
                offset(r = carrier_clearance)
                    carrier_profile_2d();
            }
}

module skid_pad(y_offset) {
    // Ski shape: full skid_h at the trailing edge, tapering so the
    // BOTTOM lifts upward toward the leading (high-X) edge — like a ski
    // tip — while the top stays level. Bridges track-piece seams instead
    // of catching on them.
    x0 = deck_front - skid_len;
    x1 = deck_front;
    translate([0, y_offset - skid_w/2, 0])
        hull() {
            translate([x0, 0, 0])
                cube([1, skid_w, skid_h]);
            translate([x1 - 1, 0, skid_h - ski_tip_r*2])
                cube([1, skid_w, ski_tip_r*2]);
        }
}

module skids() {
    y = (front_track_width - skid_w) / 2;
    skid_pad(y);
    skid_pad(-y);
}

module pico_mount() {
    // Pico 2 W sits on TOP of the deck, ROTATED 90° so its 51mm long axis
    // runs ACROSS the deck (Y) instead of along it (X) — even with the
    // fixture elongated for the carrier interface, the Pico zone between
    // it and the flare is still narrow. This costs Y-margin instead (51mm
    // board in a 55mm-wide spine — only ~2mm clearance each side, snug but
    // workable for a first pass; revisit if the real board+header
    // footprint needs more).
    px = (carrier_zone_len + flare_start) / 2;
    translate([px - pico_w/2, -pico_l/2, skid_h + deck_t])
        color("ForestGreen") cube([pico_w, pico_l, 1.2]);
    for (xs = [-1, 1], ys = [-1, 1])
        translate([px + xs*pico_hole_dy/2, ys*pico_hole_dx/2, skid_h])
            cylinder(d = pico_hole_d + 3, h = deck_t + 3);
}

module icm_mount() {
    // ICM-42688-P sits on top of the deck, in the flare zone where there's
    // width to spare beside the (now sideways) Pico. Orientation matters
    // for the fusion loop (DESIGN.md §6) — align its axes to chassis
    // forward/lateral/vertical when it's actually placed. Offset off the
    // centerline (rather than centered) so its X range, which overlaps
    // pmw_lens_pocket()'s, doesn't land on the recessed counterbore —
    // the pocket only cuts within pmw_w of the centerline.
    px = flare_start + 8;
    py = pmw_w/2 + icm_w/2 + 3;
    translate([px - icm_l/2, py - icm_w/2, skid_h + deck_t])
        color("Orange") cube([icm_l, icm_w, icm_t]);
}

module pmw_lens_pocket() {
    // Stepped socket for the LM19-LSI lens (PMW3360 datasheet Fig. 8,
    // "Recommended Base Plate Opening") — SUBTRACTED from the deck, not
    // added to it. An outer counterbore, cut into the deck's TOP face,
    // leaves exactly pmw_base_plate_t of material where the lens flange
    // seats; a smaller inner hole then cuts the rest of the way through
    // for the actual optical path down to the track. Positioned as close
    // to the guide-pin pivot as the guide-flag mount allows (DESIGN.md
    // §2 — minimizes the lever-arm correction term).
    translate([pmw_x, 0, 0]) {
        translate([0, 0, skid_h + pmw_base_plate_t])
            linear_extrude(deck_t - pmw_base_plate_t + 0.1)
                offset(r = pmw_opening_r)
                    square([pmw_l - 2*pmw_opening_r, pmw_w - 2*pmw_opening_r], center = true);
        translate([0, 0, skid_h - 0.1])
            linear_extrude(pmw_base_plate_t + 0.2)
                offset(r = pmw_hole_r)
                    square([pmw_hole_w - 2*pmw_hole_r, pmw_hole_l - 2*pmw_hole_r], center = true);
    }
}

module pmw_chip_visual() {
    // Visual placeholder only, not a mount: the sensor PCB (LM19-LSI lens
    // clipped to its underside, datasheet Fig. 5) sits pmw_pcb_standoff
    // ABOVE the deck's top surface, not hanging below it — the lens is
    // what reaches down, through pmw_lens_pocket() above. The real
    // assembly also needs the two guide posts from datasheet Fig. 4 to
    // hold the PCB at that standoff; not modeled here yet.
    translate([pmw_x - pmw_l/2, -pmw_w/2, skid_h + deck_t + pmw_pcb_standoff])
        color("RoyalBlue") cube([pmw_l, pmw_w, pmw_pcb_t]);
}

module ir_mount() {
    // IR reflectance lap sensor, alongside the PMW3360, same standoff logic.
    py = pmw_w/2 + ir_w/2 + 3;
    translate([pmw_x - ir_l/2, py - ir_w/2, skid_h - standoff_ir - ir_module_h])
        color("Crimson") cube([ir_l, ir_w, ir_module_h]);
}

module guide_flag_mount() {
    // Placeholder socket for the stock guide-flag pivot peg — MUST
    // preserve the peg's free pivot (DESIGN.md §7); do not glue solid.
    // guide_peg_depth (7mm) is deeper than deck_t (3mm) alone, so this is
    // a raised boss standing on the deck, not just a hole bored into it.
    boss_d = guide_peg_dia + 5;
    translate([deck_front - 1, 0, skid_h])
        difference() {
            cylinder(d = boss_d, h = guide_peg_depth);
            translate([0, 0, -0.1])
                cylinder(d = guide_peg_dia + 0.3, h = guide_peg_depth + 0.2);
        }
}

difference() {
    union() {
        color("LightGray") deck();
        color("DimGray") carrier_interface();
        color("Black") skids();
        pico_mount();
        icm_mount();
        ir_mount();
        color("Silver") guide_flag_mount();
        pmw_chip_visual();
    }
    pmw_lens_pocket();
}
