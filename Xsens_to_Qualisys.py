import asyncio
import qtm_rt
import sys
import keyboard
from xdpchandler import XdpcHandler

# Initialisation des variables
xdpc_handler = None
connected_devices = []
qtm_connection = None  # Stocke la connexion à QTM


def initialize_sdk():
    """Initialisation du SDK Movella DOT"""
    global xdpc_handler
    print("⚙️ Initialisation du SDK Movella DOT...")
    xdpc_handler = XdpcHandler()
    if not xdpc_handler.initialize():
        print("🔴 Échec de l'initialisation du SDK. Fermeture.")
        xdpc_handler.cleanup()
        sys.exit(-1)
    print("🟢 SDK initialisé avec succès.")


def scan_for_dots(scan_duration=60, verbose=True):
    global xdpc_handler

    if verbose:
        print(
            f"Lancement du scan des capteurs pour {scan_duration} secondes...")

    xdpc_handler.scanForDots()
    detected_dots = xdpc_handler.detectedDots()

    if not detected_dots:
        if verbose:
            print("Aucun capteur Movella DOT détecté. Fermeture.")
        xdpc_handler.cleanup()
        exit(-1)

    if verbose:
        print(f"Capteurs détectés ({len(detected_dots)} au total) :")
        for i, device in enumerate(detected_dots):
            print(f"{i + 1}. Adresse Bluetooth : {device.bluetoothAddress()}")

    return detected_dots


def connect_dots(detected_dots, verbose=True):
    global xdpc_handler, connected_devices

    if verbose:
        print("Sélectionnez les capteurs à connecter :")

    for i, device in enumerate(detected_dots):
        print(f"{i + 1}. Adresse Bluetooth : {device.bluetoothAddress()}")

    selected_indices = input(
        "Entrez les indices des capteurs à connecter (séparés par des virgules) : ")
    selected_indices = [
        int(i.strip()) - 1 for i in selected_indices.split(",") if i.strip().isdigit()]

    connected_devices = []

    for index in selected_indices:
        if 0 <= index < len(detected_dots):
            device_info = detected_dots[index]
            if verbose:
                print(
                    f"Connexion au capteur : {device_info.bluetoothAddress()}...")

            if not xdpc_handler.manager().openPort(device_info):
                if verbose:
                    print(
                        f"Échec de la connexion au capteur : {device_info.bluetoothAddress()}.")
            else:
                device = xdpc_handler.manager().device(device_info.deviceId())
                if device:
                    if verbose:
                        print(
                            f"Connecté au capteur : {device.deviceTagName()} ({device.bluetoothAddress()}).")
                    connected_devices.append(device)
        else:
            if verbose:
                print(f"Index invalide : {index + 1}. Capteur ignoré.")

    if verbose:
        print(f"{len(connected_devices)} capteur(s) connecté(s) avec succès.")

    return connected_devices


def synchronize_devices(verbose=True, max_retries=3):
    global xdpc_handler, connected_devices

    if len(connected_devices) < 2:
        if verbose:
            print("La synchronisation nécessite au moins deux capteurs connectés.")
        return False

    xdpc_handler.manager().stopSync()
    root_device = connected_devices[0]
    root_address = root_device.bluetoothAddress()

    if verbose:
        print(f"Capteur maître pour la synchronisation : {root_address}")

    success = False
    for attempt in range(max_retries):
        if verbose:
            print(
                f"Tentative de synchronisation ({attempt + 1}/{max_retries})...")

        if xdpc_handler.manager().startSync(root_address):
            success = True
            if verbose:
                print("Synchronisation réussie !")
            break
        else:
            if verbose:
                print(
                    f"Échec de la synchronisation. Raison : {xdpc_handler.manager().lastResultText()}")

    if not success and verbose:
        print("Échec de la synchronisation après plusieurs tentatives.")

    return success


async def connect_to_qtm():
    """Connexion à QTM"""
    global qtm_connection
    print("🔗 Connexion à QTM...")
    qtm_connection = await qtm_rt.connect("127.0.0.1")
    if qtm_connection is None:
        print("🔴 Échec de la connexion à QTM.")
        return False
    print("🟢 Connecté à QTM.")
    return True


async def take_control(password="Kiks"):
    """Prendre le contrôle de QTM"""
    global qtm_connection
    if qtm_connection is None:
        print("⚠️ Impossible de prendre le contrôle : connexion QTM absente.")
        return False

    success = await qtm_connection.take_control(password)
    if success:
        print("🟢 Contrôle pris sur QTM.")
        return True
    else:
        print("🔴 Échec de la prise de contrôle.")
        return False


async def start_streaming():
    """Démarrer le streaming de QTM"""
    global qtm_connection
    if qtm_connection is None:
        print("⚠️ Impossible de démarrer le streaming : connexion QTM absente.")
        return False
    print("📡 Démarrage du streaming...")
    await qtm_connection.start(rtfromfile=False)
    print("🟢 Streaming en cours...")


async def stop_streaming():
    """Arrêter le streaming de QTM"""
    global qtm_connection
    if qtm_connection is None:
        print("⚠️ Impossible d'arrêter le streaming : connexion QTM absente.")
        return False
    print("🛑 Arrêt du streaming...")
    await qtm_connection.stop()
    print("🔴 Streaming arrêté.")


def start_xsens_recording():
    """Démarrer l'enregistrement des capteurs Movella DOT"""
    print("▶️ Démarrage de l'enregistrement des IMUs...")
    for device in connected_devices:
        device.startRecording()
    print("🟢 Enregistrement en cours...")


def stop_xsens_recording():
    """Arrêter l'enregistrement des capteurs Movella DOT"""
    print("🛑 Arrêt de l'enregistrement des IMUs...")
    for device in connected_devices:
        device.stopRecording()
    print("🔴 Enregistrement arrêté.")


async def main():
    """Fonction principale"""
    global qtm_connection

    # Initialisation et connexion aux capteurs
    initialize_sdk()
    detected_dots = scan_for_dots()
    connected_devices = connect_dots(detected_dots)
    synchronize_devices(connected_devices)

    # Connexion à QTM et prise de contrôle
    await connect_to_qtm()
    await take_control()

    # Boucle principale d'attente des commandes
    while True:
        print("🔹 Appuyez sur 'r' pour démarrer l'enregistrement.")
        print("🔹 Appuyez sur 's' pour arrêter l'enregistrement.")

        key = keyboard.read_event().name  # Attente d'une touche
        if key == "r":

            # Vérifier l'état des capteurs avant de lancer QTM
            # Hypothèse : `.isRecording()` existe
            start_xsens_recording()
            await start_streaming()
            print("✅ Enregistrement et streaming démarrés.")

        elif key == "s":
            stop_xsens_recording()
            await stop_streaming()
            print("✅ Enregistrement et streaming arrêtés.")
            break

    # Fermeture propre
    qtm_connection.disconnect()
    print("✅ Déconnecté de QTM.")
    xdpc_handler.manager().stopSync()
    print("✅ Synchronisation des capteurs arrêtée.")
    xdpc_handler.cleanup()
    print("✅ SDK Movella DOT fermé.")
    sys.exit(0)


if __name__ == "__main__":
    asyncio.run(main())
