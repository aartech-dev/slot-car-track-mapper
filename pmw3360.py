"""PMW3360 optical flow sensor driver (SPI), for the track-mapper fusion loop.

Register map, timing constants, and the init/motion-burst sequence follow
the widely-ported open-source PMW3360 reference driver (SunjunKim's Arduino
library and its many forks) -- not independently verified against the
datasheet on real hardware. Check timing constants and SROM_FIRMWARE before
trusting this on a board.
"""

from machine import Pin
import time

REG_PRODUCT_ID = 0x00
REG_REVISION_ID = 0x01
REG_MOTION = 0x02
REG_DELTA_X_L = 0x03
REG_DELTA_X_H = 0x04
REG_DELTA_Y_L = 0x05
REG_DELTA_Y_H = 0x06
REG_SQUAL = 0x07
REG_CONFIG1 = 0x0F
REG_CONFIG2 = 0x10
REG_SROM_ENABLE = 0x13
REG_SROM_ID = 0x2A
REG_POWER_UP_RESET = 0x3A
REG_MOTION_BURST = 0x50
REG_SROM_LOAD_BURST = 0x62

EXPECTED_PRODUCT_ID = 0x42

# Placeholder -- NOT the real PMW3360 SROM firmware. Every reference driver
# uploads one (see module docstring); a wrong/missing one means the sensor
# will not track reliably, or at all. Source the real bytes from a verified
# driver (e.g. convert SunjunKim/PMW3360_Arduino's firmware header the same
# way a6_binary.py did for the ADNS-9800) before relying on this.
SROM_FIRMWARE = bytes([0x00] * 4094)


class PMW3360:
    def __init__(self, spi, cs_pin, cpi=3000):
        self.spi = spi
        self.cs = Pin(cs_pin, Pin.OUT, value=1)
        self.cpi = cpi

    def _write(self, reg, value):
        self.cs.value(0)
        self.spi.write(bytes([reg | 0x80, value]))
        time.sleep_us(20)
        self.cs.value(1)
        time.sleep_us(100)

    def _read(self, reg):
        self.cs.value(0)
        self.spi.write(bytes([reg & 0x7F]))
        time.sleep_us(160)
        value = self.spi.read(1)[0]
        self.cs.value(1)
        time.sleep_us(19)
        return value

    def _upload_srom(self):
        self._write(REG_CONFIG2, 0x00)
        self._write(REG_SROM_ENABLE, 0x1D)
        time.sleep_ms(10)
        self._write(REG_SROM_ENABLE, 0x18)

        self.cs.value(0)
        self.spi.write(bytes([REG_SROM_LOAD_BURST | 0x80]))
        time.sleep_us(15)
        for byte in SROM_FIRMWARE:
            self.spi.write(bytes([byte]))
            time.sleep_us(15)
        self.cs.value(1)
        time.sleep_us(200)

        srom_id = self._read(REG_SROM_ID)
        self._write(REG_CONFIG2, 0x00)
        return srom_id

    def begin(self):
        self.cs.value(1)
        self._write(REG_POWER_UP_RESET, 0x5A)
        time.sleep_ms(50)
        for reg in (REG_MOTION, REG_DELTA_X_L, REG_DELTA_X_H, REG_DELTA_Y_L, REG_DELTA_Y_H):
            self._read(reg)

        srom_id = self._upload_srom()
        time.sleep_ms(10)

        product_id = self._read(REG_PRODUCT_ID)
        if product_id != EXPECTED_PRODUCT_ID:
            raise RuntimeError("PMW3360 not detected (product ID 0x%02x, expected 0x%02x)" % (product_id, EXPECTED_PRODUCT_ID))
        if srom_id == 0:
            raise RuntimeError("PMW3360 SROM upload failed (SROM ID read back as 0)")

        cpi_value = max(0, min(119, self.cpi // 100 - 1))
        self._write(REG_CONFIG1, cpi_value)
        return product_id, srom_id

    def read_motion(self):
        """Return (dx, dy) in raw sensor counts accumulated since the last call."""
        self.cs.value(0)
        self.spi.write(bytes([REG_MOTION_BURST]))
        time.sleep_us(35)
        data = self.spi.read(12)
        self.cs.value(1)
        time.sleep_us(1)

        dx = data[2] | (data[3] << 8)
        dy = data[4] | (data[5] << 8)
        if dx >= 32768:
            dx -= 65536
        if dy >= 32768:
            dy -= 65536
        return dx, dy

    def counts_to_mm(self, counts):
        return counts / self.cpi * 25.4
