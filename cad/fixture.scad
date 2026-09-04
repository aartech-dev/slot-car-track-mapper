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
// STATUS: second pass. All donor-chassis dimensions below are now from
// calipers on the real part (not photo estimates). Still NOT print-ready:
// the component footprints (Pico/PMW3360/ICM-42688-P/IR module) are still
// typical/placeholder values — verify those against the actual parts
// bought before printing, and the rear_splice() joint is still a
// placeholder lap joint pending the real spine cross-section/rib profile.
// ======================================================================

// ---- MEASURED on the physical chassis (trust these) -------------------
wheelbase           = 114.25;
front_track_width   = 77.83;  // outside-to-outside, stock front wheels
rear_track_width    = 80.72;  // outside-to-outside, stock rear wheels (kept stock — informational only)
spine_width         = 55.0;   // width of the main chassis spine at the cut
cut_to_front_axle   = 47.0;   // V score-line to (former) front axle centerline
front_axle_to_guide = 18.0;   // front axle centerline to guide-flag tip
spine_thickness     = 3.6;    // stock spine plastic thickness at the cut face
guide_peg_dia       = 3.8;    // stock guide-flag pivot peg diameter
guide_peg_depth     = 7.0;    // stock guide-flag pivot peg engagement depth

// ---- Still estimated/typical — nothing left here as of the latest caliper pass,
// keep this section for whatever gets re-estimated later. ---------------

total_length = cut_to_front_axle + front_axle_to_guide;
// NOTE: the real total_length (65mm) is barely half of the ~112mm first-pass
// guess. That's tight — the Pico 2 W's 51mm length alone eats most of it if
// mounted lengthwise, which is why it's mounted ROTATED 90° below (across
// the deck's width instead of along its length).

// Lever arm from the guide-pin pivot (DESIGN.md §2) to wherever the
// optical sensor actually ends up — feed this into the fusion loop's
// lever-arm correction once it's finalized here.
pmw_x = total_length - 18;
lever_arm_r = total_length - pmw_x;

// ---- Component footprints — VERIFY against the specific parts bought --
pico_l = 51; pico_w = 21;                                  // Pico 2 W board outline
pico_hole_dx = 47; pico_hole_dy = 17; pico_hole_d = 2.5;    // mount-hole pattern (+ clearance)

pmw_l = 21; pmw_w = 21; pmw_module_h = 6;                  // PMW3360 breakout, typical (PCB+lens)
pmw_focus_height = 2.4;                                     // lens-to-surface distance, typical — shim to tune

icm_l = 15; icm_w = 15; icm_t = 3;                         // ICM-42688-P breakout, typical

ir_l = 32; ir_w = 10; ir_module_h = 5;                     // TCRT5000-style reflectance module, typical
ir_focus_height = 3.0;                                      // typical optimal sensing distance — verify vs. datasheet

// ---- Fixture structural parameters -------------------------------------
deck_t    = 3;    // main deck thickness
skid_h    = 9;    // ground clearance: track surface to underside of deck
skid_w    = 6;    // each skid pad's width (Y)
skid_len  = 14;   // each skid pad's length (X) — shrunk to fit the real (shorter) total_length
ski_tip_r = 3;    // radius rounding the skid's leading edge, so it bridges track-piece seams

standoff_pmw = skid_h - pmw_focus_height - pmw_module_h;
standoff_ir  = skid_h - ir_focus_height  - ir_module_h;

echo(str("total_length = ", total_length, " mm"));
echo(str("lever_arm_r (guide pivot to PMW3360) = ", lever_arm_r, " mm"));
echo(str("pmw standoff spacer needed = ", standoff_pmw, " mm ", standoff_pmw < 0 ? "*** NEGATIVE — increase skid_h or use a thinner module ***" : "(OK)"));
echo(str("ir standoff spacer needed = ", standoff_ir, " mm ", standoff_ir < 0 ? "*** NEGATIVE — increase skid_h or use a thinner module ***" : "(OK)"));

$fn = 48;

flare_start = 42;          // X where the deck begins widening from the spine to the skid track width
deck_front  = total_length - 2;  // X of the deck's front edge, almost at the guide-flag tip
splice_len  = 10;          // rear_splice overlap length — shrunk to fit the real (shorter) total_length

echo(str("usable length rear of the flare (splice + Pico zone) = ", flare_start - splice_len, " mm — Pico 2 W needs at least its short-axis dimension here since it's mounted rotated"));

// ---- Second (rear) guide — DESIGN.md §7 --------------------------------
// A dummy, mechanical-only guide behind the PMW3360, bracketing it between
// two independently-pivoting slot-engaged points. The front guide (above)
// keeps its stock role (slot engagement + power pickup via the braids);
// this one carries no current — just a hard plastic pin, free to rotate in
// its mount like the front guide's peg does. Its purpose is to make the
// sensor section's orientation depend only on the slot's geometry, not on
// the stock rear wheels' friction-dependent skid/slip through a corner,
// which the fusion model (DESIGN.md §2/§6) doesn't otherwise account for.
guide_slot_width_mm = 2.5;   // narrowest slot on the real track (given, not measured yet — confirm)
guide_pin_width_mm  = 1.0;   // hardbody-style pin, narrower than the front guide's stock peg
guide_clearance_mm  = (guide_slot_width_mm - guide_pin_width_mm) / 2;  // per side
r_worst_mm          = 221.1; // tightest curve radius across ALL FOUR lanes (red), computed
                              // directly from tmp/bolton-track.svg — NOT the ~370mm yellow-lane
                              // figure used elsewhere in this project's simulation (DESIGN.md §7/§9)

rear_guide_pin_dia = 1.2;                 // fits guide_slot_width_mm with clearance to spare
// Squeezed between rear_splice() (ends at X=splice_len) and pico_mount()'s
// board edge (starts at X=(splice_len+flare_start)/2 - pico_w/2 = 15.5) --
// checked by direct bounding-box comparison, not by eye at this scale; only
// a ~0.3mm window existed with a wider boss, hence the tighter +2mm margin
// on boss_d below instead of the guide_flag_mount()'s +5mm.
rear_guide_x       = 12.5;
front_guide_x      = deck_front - 1;      // matches guide_flag_mount()'s placement, below
guide_spacing      = front_guide_x - rear_guide_x;

// Chord-vs-arc mismatch for two independently-pivoting points rigidly
// separated by guide_spacing, both riding the same curve of radius
// r_worst_mm — this is what would force one guide against its slot wall if
// it exceeded guide_clearance_mm. (NOT the same as the larger sagitta a
// rigid, non-pivoting structural member would see over the same span — no
// such member exists here, only the two pivoting pins themselves reach
// into the slot.)
chord_arc_mismatch_mm = pow(guide_spacing, 3) / (24 * pow(r_worst_mm, 2));

echo(str("guide spacing (front pivot to rear pivot) = ", guide_spacing, " mm"));
echo(str("worst-case chord/arc mismatch @ r=", r_worst_mm, "mm = ", chord_arc_mismatch_mm,
    " mm (", chord_arc_mismatch_mm / guide_clearance_mm * 100, "% of ", guide_clearance_mm, "mm budget) ",
    chord_arc_mismatch_mm > guide_clearance_mm ? "*** EXCEEDS BUDGET -- shorten guide_spacing or re-check r_worst_mm ***" : "(OK, comfortable margin)"));

module deck() {
    // Constant-width rear section at the spine width (mates with the
    // rear splice), then flares out to front_track_width so the skids
    // (placed at the stock front track width for roll stability, DESIGN.md
    // §7) actually land on structure instead of floating past the edge of
    // a 55mm-wide deck — the same reason the stock chassis needs separate
    // lateral arms to reach its wheels from the narrow spine.
    translate([10, -spine_width/2, skid_h])
        cube([flare_start - 10, spine_width, deck_t]);
    hull() {
        translate([flare_start, -spine_width/2, skid_h])
            cube([0.1, spine_width, deck_t]);
        translate([deck_front, -front_track_width/2, skid_h])
            cube([0.1, front_track_width, deck_t]);
    }
}

module rear_splice() {
    // Overlap tab that mates with the stock spine stub left on the rear
    // (motor/drive) section after the cut. Placeholder lap joint —
    // measure the real stub's thickness/rib profile and redesign this
    // as a proper tongue-and-groove or screwed lap joint.
    translate([0, -spine_width/2, skid_h])
        cube([splice_len, spine_width, spine_thickness + 2]);
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
    // runs ACROSS the deck (Y) instead of along it (X) — the real
    // total_length (65mm) is too short to fit the board lengthwise once
    // the rear splice and front sensor/guide-flag cluster take their
    // share. This costs Y-margin instead (51mm board in a 55mm-wide
    // spine — only ~2mm clearance each side, snug but workable for a
    // first pass; revisit if the real board+header footprint needs more).
    px = (splice_len + flare_start) / 2;
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
    // forward/lateral/vertical when it's actually placed.
    px = flare_start + 8;
    translate([px - icm_l/2, -icm_w/2, skid_h + deck_t])
        color("Orange") cube([icm_l, icm_w, icm_t]);
}

module pmw_mount() {
    // PMW3360 hangs below the deck, lens facing down, as close to the
    // guide-pin pivot as the guide-flag mount allows (DESIGN.md §2 —
    // minimizes the lever-arm correction term). Standoff height sets
    // the focus distance; shim to tune once assembled.
    translate([pmw_x - pmw_l/2, -pmw_w/2, skid_h - standoff_pmw - pmw_module_h])
        color("RoyalBlue") cube([pmw_l, pmw_w, pmw_module_h]);
}

module ir_mount() {
    // IR reflectance lap sensor, alongside the PMW3360, same standoff logic.
    py = pmw_w/2 + ir_w/2 + 3;
    translate([pmw_x - ir_l/2, py - ir_w/2, skid_h - standoff_ir - ir_module_h])
        color("Crimson") cube([ir_l, ir_w, ir_module_h]);
}

module rear_guide_mount() {
    // Second, dummy guide (DESIGN.md §7) — a hard plastic pin, no wiring,
    // free to pivot in its mount (NOT glued solid — same rule as the front
    // guide flag). Positioned to bracket the PMW3360 (at pmw_x) between the
    // two guides.
    boss_d = rear_guide_pin_dia + 2;  // tight clearance to the rear_splice()/pico_mount() gap -- see rear_guide_x
    translate([rear_guide_x, 0, skid_h])
        difference() {
            cylinder(d = boss_d, h = 5);
            translate([0, 0, -0.1])
                cylinder(d = rear_guide_pin_dia + 0.3, h = 5.2);
        }
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

union() {
    color("LightGray") deck();
    color("DimGray") rear_splice();
    color("Black") skids();
    pico_mount();
    icm_mount();
    pmw_mount();
    ir_mount();
    color("Silver") guide_flag_mount();
    color("Silver") rear_guide_mount();
}
