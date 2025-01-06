import asyncio
from bleak import BleakScanner, BleakClient
# Assurez-vous que cette importation est correcte
from dot_tools import BatteryCharacteristic


def filter_devices(device):
    return device.name == "Movella DOT"


async def connect_to_device(device):
    """
    Tentative de connexion à un périphérique Bluetooth Movella DOT.
    Affiche le niveau de batterie en cas de connexion réussie.
    """
    async with BleakClient(device.address) as client:
        if client.is_connected:
            print(f"Connecté à l'IMU : {device.address}")
            try:
                # Lecture du niveau de batterie
                battery_data = await client.read_gatt_char(BatteryCharacteristic.UUID)
                battery = BatteryCharacteristic.from_bytes(battery_data)
                print(
                    f"Niveau de batterie : {battery.battery_level}% ({'en charge' if battery.charging_status else 'non en charge'})")
            except Exception as e:
                print(f"Impossible de lire le niveau de batterie : {e}")
        else:
            print(f"Échec de connexion à l'IMU : {device.address}")


async def scan_continuously():
    print("Scanning for 'Movella DOT' devices. Press Ctrl+C to stop.")
    seen_devices = set()
    try:
        while True:
            devices = await BleakScanner.discover()
            new_devices = [device for device in devices if filter_devices(
                device) and device.address not in seen_devices]
            for device in new_devices:
                print(
                    f"Found new device: {device.name} - Address: {device.address}")
                seen_devices.add(device.address)

                # Demande de connexion
                user_input = input(
                    f"Voulez-vous vous connecter à l'appareil {device.address} ? (y/n) : ").strip().lower()
                if user_input == "y":
                    await connect_to_device(device)
                else:
                    print(f"Connexion à {device.address} ignorée.")

            await asyncio.sleep(1)  # Wait 1 second before rescanning
    except KeyboardInterrupt:
        print("Scanning stopped.")

if __name__ == "__main__":
    asyncio.run(scan_continuously())
