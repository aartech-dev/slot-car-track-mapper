from machine import Pin, SPI
import time

# SPI Setup
SPI_CLK = 10
SPI_MOSI = 11
SPI_MISO = 12
CS_PIN = 13
RESET_PIN = 14

# ADNS-9800 Registers
REG_PRODUCT_ID = 0x00
REG_MOTION = 0x02
REG_DELTA_X = 0x03
REG_DELTA_Y = 0x04
REG_SROM_ENABLE = 0x13
REG_SROM_ID = 0x2A
REG_SROM_LOAD_BURST = 0x62
REG_LASER_CTRL0 = 0x20

# SPI Initialization
spi = SPI(1, baudrate=2000000, polarity=1, phase=1, miso=Pin(SPI_MISO), mosi=Pin(SPI_MOSI), sck=Pin(SPI_CLK))
cs = Pin(CS_PIN, Pin.OUT, value=1)
reset = Pin(RESET_PIN, Pin.OUT, value=1)

def write_register(register, value):
    cs.value(0)
    spi.write(bytearray([register | 0x80, value]))  # MSB = 1 for write
    cs.value(1)
    time.sleep_us(50)

def read_register(register):
    cs.value(0)
    spi.write(bytearray([register & 0x7F]))  # MSB = 0 for read
    time.sleep_us(50)
    data = spi.read(1)
    cs.value(1)
    return data[0]

def reset_sensor():
    reset.value(0)
    time.sleep_ms(10)
    reset.value(1)
    time.sleep_ms(10)

def upload_srom(srom_data):
    write_register(REG_SROM_ENABLE, 0x1D)
    time.sleep_ms(10)

    write_register(REG_SROM_ENABLE, 0x18)
    time.sleep_ms(10)

    cs.value(0)
    spi.write(bytearray([REG_SROM_LOAD_BURST | 0x80]))  # Start burst mode write
    time.sleep_us(15)

    for byte in srom_data:
        spi.write(bytearray([byte]))
        time.sleep_us(15)

    cs.value(1)
    time.sleep_ms(10)

def read_motion():
    motion = read_register(REG_MOTION)
    if motion & 0x80:  # Motion detected
        delta_x = read_register(REG_DELTA_X)
        delta_y = read_register(REG_DELTA_Y)
        return (delta_x, delta_y)
    return (0, 0)

# --- Main Execution ---
reset_sensor()

# Check product ID
prod_id = read_register(REG_PRODUCT_ID)
if prod_id != 0x33:
    print(f"Error: Unexpected Product ID {prod_id:#02x}")
else:
    print(f"ADNS-9800 detected! Product ID: {prod_id:#02x}")

# Load SROM (You need to replace 'srom_data' with actual SROM file contents)
srom_data = bytes([0x00] * 4094)  # Replace this with real SROM data
upload_srom(srom_data)

# Verify SROM
srom_id = read_register(REG_SROM_ID)
if srom_id == 0:
    print("Error: SROM upload failed.")
else:
    print(f"SROM successfully loaded. ID: {srom_id:#02x}")

# Enable Laser
write_register(REG_LASER_CTRL0, 0x80)  # Enable laser

# Main Loop to Read Motion
while True:
    dx, dy = read_motion()
    if dx != 0 or dy != 0:
        print(f"Motion detected: ΔX={dx}, ΔY={dy}")
    time.sleep(0.1)
