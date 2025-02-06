import asyncio
import time
import threading
import qtm_rt
from xdpchandler import XdpcHandler

""" Script qui permet de : 
- Scanner les capteurs Movella DOT
- Se connecter aux capteurs Movella DOT
- Synchroniser les capteurs Movella DOTnt
- Démarrer l'enregistrement des capteurs Movella DOT suite à l'événement EventRTfromFileStarted # ou EventCaptureStarted
- Arrêter l'enregistrement des capteurs Movella DOT suite à l'événement EventRTfromFileStopped ou EventCaptureStopped
"""

# Initialisation globale des variables
xdpc_handler = None
connected_devices = []


def initialize_sdk(verbose=True):
    global xdpc_handler
    if verbose:
        print("Initialisation du SDK Movella DOT...")

    xdpc_handler = XdpcHandler()

    if not xdpc_handler.initialize():
        if verbose:
            print("Échec de l'initialisation du SDK. Fermeture.")
        xdpc_handler.cleanup()
        exit(-1)

    if verbose:
        print("SDK initialisé avec succès.")

    return xdpc_handler


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


async def start_synchronized_recording(duration=5000, verbose=True):
    global connected_devices

    if verbose:
        print("Démarrage de l'enregistrement des capteurs Movella DOT...")

    for device in connected_devices:
        if not device.startTimedRecording(duration):
            print(
                f"Impossible de démarrer l'enregistrement pour {device.bluetoothAddress()}. Raison : {device.lastResultText()}")
        else:
            print(f"Enregistrement démarré pour {device.bluetoothAddress()}.")


async def stop_synchronized_recording(verbose=True):
    global connected_devices

    if verbose:
        print("Arrêt de l'enregistrement des capteurs Movella DOT...")

    for device in connected_devices:
        try:
            device.stopRecording()
            print(f"Enregistrement arrêté pour {device.bluetoothAddress()}.")
        except Exception as e:
            print(
                f"Erreur lors de l'arrêt de l'enregistrement pour {device.bluetoothAddress()}: {e}")


async def on_event(event):
    """
    Gestionnaire des événements reçus de QTM.
    Déclenche l'enregistrement des IMUs lorsque EventRTfromFileStarted est reçu
    et l'arrêt des IMUs lorsque EventRTfromFileStopped est reçu.
    """
    print(f"Événement reçu depuis QTM : {event}")

    if event == qtm_rt.QRTEvent.EventCaptureStarted:  # ou EventCaptureStarted # EventRTfromFileStarted
        # "Evenement : Capture démarrée. Démarrage des capteurs Movella."
        print("Événement : Lecture en temps réel démarrée. Démarrage des capteurs Movella.")
        await start_synchronized_recording(duration=5000, verbose=True)
        print("Enregistrement des capteurs Movella démarré.")

    elif event == qtm_rt.QRTEvent.EventCaptureStopped:  # ou EventCaptureStopped # EventRTfromFileStopped
        # "Evenement : Capture arrêtée. Arrêt des capteurs Movella."
        print("Événement : Lecture en temps réel arrêtée. Arrêt des capteurs Movella.")
        await stop_synchronized_recording(verbose=True)
        print("Enregistrement des capteurs Movella arrêté.")

    else:
        print(f"Événement non géré ou inconnu : {event}")


async def connect_to_qtm():
    """
    Se connecte à QTM et écoute les événements.
    """
    try:
        print("Connexion à QTM...")
        connection = await qtm_rt.connect(
            "127.0.0.1",
            on_event=lambda event: asyncio.create_task(
                on_event(event))  # Correctif
        )
        if connection is None:
            print("Échec de la connexion à QTM.")
            return

        print("Connexion à QTM établie. En attente des événements...")
        while True:
            await asyncio.sleep(.1)
    except Exception as e:
        print(f"Erreur lors de la connexion à QTM : {e}")


if __name__ == "__main__":
    verbose = True
    initialize_sdk(verbose=verbose)
    detected_dots = scan_for_dots(scan_duration=1000, verbose=verbose)
    connect_dots(detected_dots, verbose=verbose)
    synchronize_devices(verbose=verbose)

    asyncio.run(connect_to_qtm())
