import asyncio
import time
import threading
import qtm_rt
import sys
import keyboard
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


async def start_qtm_capture():
    """
    Démarre la capture QTM si la connexion est active.
    """
    global qtm_connection

    if qtm_connection is not None:
        print("🟢 Démarrage de la capture dans QTM...")
        await qtm_connection.start(rtfromfile=False)  # Démarrer la capture
    else:
        print("🔴 Impossible de démarrer QTM : connexion non établie.")


async def start_synchronized_recording(duration=5000, verbose=True):
    """
    Démarre l'enregistrement des capteurs Movella DOT.
    Si au moins un capteur démarre, on envoie une commande à QTM pour commencer la capture.
    """
    global connected_devices, xsens_recording

    if verbose:
        print("▶️ Démarrage de l'enregistrement des capteurs Movella DOT...")

    started = False  # Vérifier si au moins un capteur a réussi à enregistrer

    for device in connected_devices:
        if not device.startTimedRecording(duration):
            print(
                f"❌ Échec de l'enregistrement pour {device.bluetoothAddress()}. Raison : {device.lastResultText()}")
        else:
            print(
                f"✅ Enregistrement démarré pour {device.bluetoothAddress()}.")
            started = True

    # Si au moins un capteur enregistre et que QTM est bien connecté, on démarre QTM
    if started and not xsens_recording and qtm_connection is not None:
        xsens_recording = True
        await start_qtm_capture()  # Lancer la capture QTM


async def stop_synchronized_recording(verbose=True):
    """
    Arrête l'enregistrement des capteurs Movella DOT.
    """
    global connected_devices, xsens_recording

    if verbose:
        print("⏹️ Arrêt de l'enregistrement des capteurs Movella DOT...")

    for device in connected_devices:
        try:
            device.stopRecording()
            print(f"✅ Enregistrement arrêté pour {device.bluetoothAddress()}.")
        except Exception as e:
            print(
                f"❌ Erreur lors de l'arrêt de l'enregistrement pour {device.bluetoothAddress()}: {e}")

    xsens_recording = False  # Réinitialiser le statut d'enregistrement


async def stop_qtm_capture():
    """
    Arrête la capture QTM proprement si la connexion est active.
    """
    global qtm_connection

    if qtm_connection is not None:
        print("🛑 Arrêt de la capture QTM...")
        await qtm_connection.stop()
    else:
        print("🔴 Impossible d'arrêter QTM : connexion non établie.")


async def on_event(event):
    """
    Écoute les événements de QTM en continu.
    """
    print(f"📡 Événement reçu depuis QTM : {event}")

    if event == qtm_rt.QRTEvent.EventCaptureStarted:
        print("🟢 QTM a confirmé que la capture a bien démarré.")

    elif event == qtm_rt.QRTEvent.EventCaptureStopped:
        print("🛑 QTM a arrêté la capture.")

    else:
        print(f"ℹ️ Événement inconnu : {event}")


async def connect_to_qtm():
    """
    Se connecte à QTM et écoute les événements.
    """
    global qtm_connection
    try:
        print("🔗 Connexion à QTM...")
        qtm_connection = await qtm_rt.connect(
            "127.0.0.1",
            on_event=lambda event: asyncio.create_task(on_event(event))
        )
        if qtm_connection is None:
            print("🔴 Échec de la connexion à QTM.")
            return

        print("✅ Connexion à QTM établie. En attente des événements...")
        while True:
            await asyncio.sleep(0.1)
    except Exception as e:
        print(f"❌ Erreur lors de la connexion à QTM : {e}")


def stop_execution():
    """
    Fonction pour arrêter le programme proprement.
    """
    print("❌ Arrêt du programme...")
    asyncio.run(stop_synchronized_recording(verbose=True))  # Arrêter les Xsens
    asyncio.run(stop_qtm_capture())  # Arrêter QTM
    sys.exit(0)  # Quitter le script proprement


def user_input_listener():
    """
    Écoute les touches 'l' (lancer enregistrement), 's' (stopper enregistrement), et 'q' (quitter).
    """
    print("🔹 Appuyez sur 'l' pour démarrer l'enregistrement des Xsens et QTM")
    print("🔹 Appuyez sur 's' pour arrêter l'enregistrement des Xsens")
    print("🔹 Appuyez sur 'q' pour quitter le programme")

    while True:
        try:
            if keyboard.is_pressed("l"):
                print("⌛ Démarrage enregistrement...")
                asyncio.run(start_synchronized_recording(
                    duration=5000, verbose=True))
            elif keyboard.is_pressed("s"):
                print("🛑 Arrêt enregistrement...")
                asyncio.run(stop_synchronized_recording(verbose=True))
            elif keyboard.is_pressed("q"):
                print("❌ Arrêt du programme...")
                stop_execution()
            time.sleep(0.2)  # Petit délai pour éviter trop de déclenchements
        except:
            pass


if __name__ == "__main__":
    verbose = True
    initialize_sdk(verbose=verbose)
    detected_dots = scan_for_dots(scan_duration=1000, verbose=verbose)
    connect_dots(detected_dots, verbose=verbose)
    synchronize_devices(verbose=verbose)

    # Lancer l'écoute de QTM en parallèle
    qtm_thread = threading.Thread(
        target=asyncio.run, args=(connect_to_qtm(),), daemon=True)
    qtm_thread.start()

    # Lancer l'écoute des entrées utilisateur
    user_input_listener()
