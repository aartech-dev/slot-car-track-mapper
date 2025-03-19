import network
import asyncio
import logging



class WiFiManager:
    def __init__(self, networks):
        """Initialize the WiFi Manager with a list of known networks."""
        self.networks = networks
        self.wlan = network.WLAN(network.STA_IF)
        self.wlan.active(True)

    async def connect(self):
        """Try to connect to known WiFi networks asynchronously."""
        for net in self.networks:
            ssid, password = net["ssid"], net["password"]
            print(f"Trying to connect to {ssid}...")
            self.wlan.connect(ssid, password)

            for _ in range(10):  # Try for 10 iterations (20 seconds total)
                if self.wlan.isconnected():
                    print(f"Connected to {ssid}!")
                    print("IP Address:", self.wlan.ifconfig()[0])
                    return True
                await asyncio.sleep(2)

            print(f"Failed to connect to {ssid}. Trying next...")

        print("No WiFi networks available!")
        return False

    async def monitor(self, interval=5):
        """Continuously check WiFi status and reconnect if needed."""
        while True:
            if not self.wlan.isconnected():
                print("WiFi lost! Reconnecting...")
                self.wlan.disconnect()
                await asyncio.sleep(2)
                await self.connect()
            await asyncio.sleep(interval)

    def get_ip(self):
        """Return the current IP address, or None if disconnected."""
        return self.wlan.ifconfig()[0] if self.wlan.isconnected() else None

# List of WiFi networks (SSID and Password)
WIFI_NETWORKS = [
    {"ssid": "PrimaryWiFi", "password": "PrimaryPassword"},
    {"ssid": "BackupWiFi", "password": "BackupPassword"}
]

async def main():
    """Main function to start WiFi Manager."""
    wifi = WiFiManager(WIFI_NETWORKS)
    
    if await wifi.connect():
        print("Starting WiFi monitor...")
        await wifi.monitor()
    else:
        print("Could not connect to any network.")

# Run the async event loop
asyncio.run(main())
