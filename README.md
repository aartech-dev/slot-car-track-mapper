# slot-car-track-mapper
Design for a device for mapping a slot car track by using a part from an optical mouse.


## Links

https://www.application-datasheet.com/pdf/broadcom/adns-6190-002.pdf   

https://www.snapeda.com/parts/ADNS-9800/PixArt/datasheet/   

https://www.tindie.com/products/citizenjoe/adns-9800-motion-sensor/   

https://www.reddit.com/r/Trackballs/comments/ovn849/sharing_adns9800_and_pmw3360_breakout_boards_on/   

https://sminliwu.github.io/2019/04/30/adns.html

https://github.com/kbjunky/ADNS9800   

http://pepijndevos.nl/2015/05/29/adns-9800-hookup-guide.html  

https://www.instructables.com/Arduino-Tutorial-ADNS-9800-Laser-Mouse-Traveled-Di/  

https://github.com/INITIAL7664/ADNS-9800/blob/master/firmware.ino

https://github.com/svofski/ADNS-9800-Energia/blob/master/ADNS-9800-Energia.ino

'''
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

'''

## How to Use

Copy the script onto your Raspberry Pi Pico using Thonny or another MicroPython editor.
Ensure you have the ADNS-9800 SROM file (from PixArt). Replace srom_data with the actual bytes from the SROM.
Run the script. If the sensor is properly connected, you should see motion data when you move it.

## Next Steps
Fine-tune DPI settings by adjusting configuration registers.
Implement more advanced features, such as lift detection or angle snapping.
Store the real SROM file in flash memory or an SD card instead of embedding it in code.

To use the ADNS-9800 SROM file in MicroPython, you need to:

Obtain the SROM file (usually a .bin file) from PixArt or an official source.
Convert it to a byte array that MicroPython can read.
Modify the script to read the file from flash storage or an SD card.

Step 1: Convert the SROM File
If you already have the ADNS9800_SROM.bin file, you need to convert it into a Python byte array. You can do this with a Python script on your computer.

Convert SROM File to Python Byte Array

Run this Python script on your computer (not on the Pico!):

# Convert ADNS-9800 SROM binary to a Python byte array
srom_filename = "ADNS9800_SROM.bin"

with open(srom_filename, "rb") as f:
    srom_data = f.read()

# Format as a Python list
output = "srom_data = bytes([" + ", ".join(f"0x{b:02X}" for b in srom_data) + "])"

# Save as a Python file
with open("srom_data.py", "w") as f:
    f.write(output)

print("Conversion complete! The SROM data is saved in 'srom_data.py'.")


This script reads the binary file and converts it into a Python byte array.
The output is stored in srom_data.py, which you can then upload to the Pico.

Step 2: Upload the SROM Data to the Pico
After running the script, copy srom_data.py to your Raspberry Pi Pico.
Modify your MicroPython script to import the SROM data instead of defining it manually.

Step 3: Modify the MicroPython Script to Use the SROM File
Change this line in your MicroPython script:

srom_data = bytes([0x00] * 4094)  # Replace this with real SROM data


To this:

from srom_data import srom_data  # Import the converted SROM data

Alternative: Read Directly from an SROM File on an SD Card
If you have an SD card connected to the Pico, you can store the ADNS9800_SROM.bin there and read it directly:

def load_srom_from_sd():
    with open("/sd/ADNS9800_SROM.bin", "rb") as f:
        return f.read()

srom_data = load_srom_from_sd()


Final Steps
Run your MicroPython script on the Pico.
The SROM should now load properly, and the sensor should start tracking motion! 🚀

import os
import sdcard
import machine
import time

# SD Card SPI Configuration
SPI_SD = machine.SPI(0, baudrate=1000000, polarity=0, phase=0,
                     sck=machine.Pin(18), mosi=machine.Pin(19), miso=machine.Pin(16))
CS_SD = machine.Pin(17, machine.Pin.OUT)

# Mount SD Card
def mount_sd():
    global sd
    try:
        sd = sdcard.SDCard(SPI_SD, CS_SD)
        vfs = os.VfsFat(sd)
        os.mount(vfs, "/sd")
        print("SD Card Mounted!")
    except Exception as e:
        print("Failed to mount SD card:", e)

# Load SROM File from SD Card
def load_srom_from_sd(filename="/sd/ADNS9800_SROM.bin"):
    try:
        with open(filename, "rb") as f:
            srom_data = f.read()
        print(f"SROM file loaded: {len(srom_data)} bytes")
        return srom_data
    except Exception as e:
        print("Error reading SROM file:", e)
        return None

# --- MAIN EXECUTION ---
mount_sd()

srom_data = load_srom_from_sd()
if srom_data:
    print("SROM Data Ready to Upload to ADNS-9800!")
else:
    print("Failed to load SROM file.")


4. Upload the SROM File to the SD Card

Format the SD card as FAT32.
Copy the ADNS9800_SROM.bin file to the root of the SD card.
Insert the SD card into the Pico SD card module.

5. Modify Your ADNS-9800 Code

Now, update your ADNS-9800 MicroPython script to read from the SD card:

Replace this:

from srom_data import srom_data  # Import the SROM from a Python file

With this:

srom_data = load_srom_from_sd()




