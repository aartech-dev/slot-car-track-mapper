"""ICM-42688-P IMU driver (I2C), gyro+accel only -- no magnetometer is used,
deliberately (see DESIGN.md SS3: the motor's magnets would corrupt it).

Register map follows the standard ICM-42688-P bank-0 layout from TDK's
reference documentation -- not independently verified against the
datasheet on real hardware.
"""

import time

WHO_AM_I = 0x75
EXPECTED_WHO_AM_I = 0x47

REG_DEVICE_CONFIG = 0x11
REG_PWR_MGMT0 = 0x4E
REG_GYRO_CONFIG0 = 0x4F
REG_ACCEL_CONFIG0 = 0x50
REG_ACCEL_DATA_X1 = 0x1F  # 12-byte burst from here: accel XYZ then gyro XYZ

GYRO_FS_2000DPS = 0x00 << 5   # GYRO_CONFIG0 FS_SEL bits
ACCEL_FS_16G = 0x00 << 5      # ACCEL_CONFIG0 FS_SEL bits
ODR_1KHZ = 0x06                # shared ODR encoding for both CONFIG0 registers

GYRO_SENSITIVITY_LSB_PER_DPS = 16.4    # for +-2000dps, per datasheet table
ACCEL_SENSITIVITY_LSB_PER_G = 2048.0   # for +-16g, per datasheet table


class ICM42688:
    def __init__(self, i2c, addr=0x68):
        self.i2c = i2c
        self.addr = addr

    def _write(self, reg, value):
        self.i2c.writeto_mem(self.addr, reg, bytes([value]))

    def _read(self, reg, n=1):
        return self.i2c.readfrom_mem(self.addr, reg, n)

    def begin(self):
        who = self._read(WHO_AM_I)[0]
        if who != EXPECTED_WHO_AM_I:
            raise RuntimeError("ICM-42688-P not detected (WHO_AM_I 0x%02x, expected 0x%02x)" % (who, EXPECTED_WHO_AM_I))

        self._write(REG_PWR_MGMT0, 0x0F)  # gyro + accel -> low-noise mode
        time.sleep_ms(50)                  # gyro settling time after enable
        self._write(REG_GYRO_CONFIG0, GYRO_FS_2000DPS | ODR_1KHZ)
        self._write(REG_ACCEL_CONFIG0, ACCEL_FS_16G | ODR_1KHZ)
        time.sleep_ms(10)
        return who

    def read_raw(self):
        """Return (ax, ay, az, gx, gy, gz) as raw signed 16-bit counts."""
        data = self._read(REG_ACCEL_DATA_X1, 12)
        values = []
        for i in range(0, 12, 2):
            v = (data[i] << 8) | data[i + 1]
            if v >= 32768:
                v -= 65536
            values.append(v)
        return tuple(values)

    def read_gyro_dps(self):
        """Return (gx, gy, gz) in degrees/second."""
        _, _, _, gx, gy, gz = self.read_raw()
        s = GYRO_SENSITIVITY_LSB_PER_DPS
        return gx / s, gy / s, gz / s

    def read_accel_g(self):
        """Return (ax, ay, az) in g."""
        ax, ay, az, _, _, _ = self.read_raw()
        s = ACCEL_SENSITIVITY_LSB_PER_G
        return ax / s, ay / s, az / s
