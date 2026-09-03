"""Track-mapper firmware: fuses the PMW3360 (translation) with the
ICM-42688-P's gyro (heading) into a dead-reckoned path, resets position at
each lap-marker crossing, and logs the result to a CSV file on the Pico's
flash. See DESIGN.md SS2 and SS6 for the fusion/lap-detection design this
implements, and SS7 for where the pin assignments and lever-arm distance
below come from.

NOT YET TESTED ON REAL HARDWARE. Known calibration steps before trusting
the output:
  - PMW3360.SROM_FIRMWARE is a placeholder (see pmw3360.py) -- the sensor
    will not track correctly, or at all, until real firmware bytes are in.
  - LAP_THRESHOLD is a guess -- print ir.read_u16() while passing the real
    marker by hand and set this from the actual light/dark ADC values.
  - Gyro sign/axis and optical dx/dy axis mapping depend on exactly how
    the ICM-42688-P and PMW3360 end up oriented on the fixture -- rotate
    the car by hand and push it straight forward by hand to confirm
    theta and (dx, dy) move the way this file assumes before trusting a
    real run (see the fusion loop below for the assumed convention).
"""

import time
import math
from machine import Pin, SPI, I2C, ADC

from pmw3360 import PMW3360
from icm42688 import ICM42688

SPI_SCK = 10
SPI_MOSI = 11
SPI_MISO = 12
PMW_CS = 13
# GPIO14 (PMW3360 MOTION) and GPIO6 (ICM interrupt) are wired but not used
# yet -- this first pass polls both sensors every loop instead.

I2C_SDA = 4
I2C_SCL = 5

IR_ADC_PIN = 26

# PMW3360-to-guide-pivot offset along the body's forward axis, from the
# fixture CAD (DESIGN.md SS2, SS7) -- re-measure if the layout changes.
LEVER_ARM_MM = 18.0

LAP_THRESHOLD = 30000    # ADC counts (0-65535) -- PLACEHOLDER, calibrate against the real marker
LAP_DEBOUNCE_MS = 1000   # ignore retriggers faster than this (DESIGN.md SS6)
LAPS_TO_RECORD = 3
MAX_RUN_MS = 5 * 60 * 1000  # safety cutoff if the lap sensor never fires

LOG_PATH = "track_log.csv"
FLUSH_EVERY = 50  # samples between flushes, so a mid-run brownout loses at most this many


def run():
    spi = SPI(1, baudrate=2_000_000, polarity=1, phase=1,
              sck=Pin(SPI_SCK), mosi=Pin(SPI_MOSI), miso=Pin(SPI_MISO))
    pmw = PMW3360(spi, PMW_CS)
    print("Initializing PMW3360...")
    product_id, srom_id = pmw.begin()
    print("PMW3360 OK: product_id=0x%02x srom_id=0x%02x" % (product_id, srom_id))

    i2c = I2C(0, sda=Pin(I2C_SDA), scl=Pin(I2C_SCL), freq=400_000)
    icm = ICM42688(i2c)
    print("Initializing ICM-42688-P...")
    who = icm.begin()
    print("ICM-42688-P OK: WHO_AM_I=0x%02x" % who)

    ir = ADC(Pin(IR_ADC_PIN))

    x = 0.0
    y = 0.0
    theta = 0.0  # radians; 0 = the heading the car is sitting at when this starts
    lap = 0
    ir_above = False
    last_lap_ms = 0
    sample_count = 0

    print("Recording -- drive %d lap(s), or waits up to %ds." % (LAPS_TO_RECORD, MAX_RUN_MS // 1000))
    start_ms = time.ticks_ms()
    t_prev = time.ticks_us()

    log = open(LOG_PATH, "w")
    log.write("t_ms,x_mm,y_mm,theta_rad,lap\n")

    try:
        while lap < LAPS_TO_RECORD:
            now_ms = time.ticks_ms()
            if time.ticks_diff(now_ms, start_ms) > MAX_RUN_MS:
                print("MAX_RUN_MS exceeded with no lap trigger -- stopping, saving what we have.")
                break

            t_now = time.ticks_us()
            dt = time.ticks_diff(t_now, t_prev) / 1_000_000
            t_prev = t_now

            _, _, gz_dps = icm.read_gyro_dps()
            gz_rad_s = math.radians(gz_dps)
            dtheta = gz_rad_s * dt
            theta += dtheta

            dx_counts, dy_counts = pmw.read_motion()
            dx_mm = pmw.counts_to_mm(dx_counts)
            dy_mm = pmw.counts_to_mm(dy_counts)

            # Recover the guide-pivot's displacement from the sensor's own,
            # using this tick's rotation (DESIGN.md SS2):
            #   v_pivot = v_sensor - omega x r,  r = (LEVER_ARM_MM, 0) body-frame
            dx_pivot = dx_mm
            dy_pivot = dy_mm - dtheta * LEVER_ARM_MM

            # Rotate the body-frame displacement into the world frame and
            # integrate (theta: 0=start heading, +ve = CCW, matches a
            # right-handed Z-up gyro axis -- flip gz's sign here if a
            # by-hand rotation test shows it backwards).
            cos_t = math.cos(theta)
            sin_t = math.sin(theta)
            x += dx_pivot * cos_t - dy_pivot * sin_t
            y += dx_pivot * sin_t + dy_pivot * cos_t

            ir_value = ir.read_u16()
            if (ir_value > LAP_THRESHOLD and not ir_above
                    and time.ticks_diff(now_ms, last_lap_ms) > LAP_DEBOUNCE_MS):
                ir_above = True
                last_lap_ms = now_ms
                lap += 1
                print("Lap %d/%d at t=%dms (drift before reset: x=%.1fmm y=%.1fmm)"
                      % (lap, LAPS_TO_RECORD, now_ms, x, y))
                x = 0.0
                y = 0.0
            elif ir_value <= LAP_THRESHOLD:
                ir_above = False

            log.write("%d,%.2f,%.2f,%.4f,%d\n" % (now_ms, x, y, theta, lap))
            sample_count += 1
            if sample_count % FLUSH_EVERY == 0:
                log.flush()
    finally:
        log.flush()
        log.close()

    print("Done: %d samples, %d lap(s) recorded to %s" % (sample_count, lap, LOG_PATH))
    print("Retrieve the file with mpremote/Thonny/ampy before power-cycling the board.")


run()
