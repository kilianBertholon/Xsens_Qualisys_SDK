import asyncio
import qtm_rt

qtm_connection = None  # Stocke la connexion à QTM


async def connect_to_qtm():
    """
    Se connecter à QTM et garder la connexion active.
    """
    global qtm_connection
    print("🔗 Tentative de connexion à QTM...")

    qtm_connection = await qtm_rt.connect("127.0.0.1")  # Connexion asynchrone

    if qtm_connection is None:
        print("🔴 Échec de la connexion à QTM.")
        return False

    print("🟢 Connecté à QTM.")
    return True  # Indique que la connexion a réussi


async def take_control(password: str):
    """ Prendre le contrôle de QTM """
    global qtm_connection

    if qtm_connection is None:
        print("⚠️ Impossible de prendre le contrôle : connexion QTM absente.")
        return

    success = await qtm_connection.take_control(password)
    if success:
        print("🟢 Contrôle pris sur QTM.")
    else:
        print("🔴 Échec de la prise de contrôle.")


async def create_new_capture():
    """ Créer une nouvelle capture dans QTM """
    global qtm_connection

    if qtm_connection is None:
        print("⚠️ Impossible de créer une capture : connexion QTM absente.")
        return

    capture = await qtm_connection.new()
    if capture is None:
        print("🔴 Échec de la création de la capture.")
    else:
        print("🟢 Nouvelle capture créée.")

    return capture


async def set_capture_parameters():
    """ Configure les paramètres de la nouvelle capture via un XML """
    global qtm_connection

    if qtm_connection is None:
        print("⚠️ Impossible de configurer la capture : connexion QTM absente.")
        return

    # Exemple de configuration en XML (à adapter selon tes besoins)
    xml_configuration = """<?xml version="1.0" encoding="UTF-8"?>
    <QTM_Settings>
        <General>
            <Capture_Time>20</Capture_Time>  <!-- Durée de la capture en secondes -->
            <Frequency>120</Frequency>  <!-- Fréquence d'acquisition -->
        </General>s
    </QTM_Settings>"""

    print("📡 Envoi des paramètres de capture à QTM...")
    response = await qtm_connection.send_xml(xml_configuration)

    if response:
        print("🟢 Paramètres de capture appliqués avec succès.")
    else:
        print("🔴 Échec de l'application des paramètres.")


async def start_streaming():
    """ Démarrer le streaming de données """
    global qtm_connection

    if qtm_connection is None:
        print("⚠️ Impossible de démarrer le streaming : connexion QTM absente.")
        return
    await qtm_connection.start(rtfromfile=False)


async def main():
    """ Fonction principale qui gère la connexion et les actions sur QTM """
    success = await connect_to_qtm()
    if not success:
        return  # Soit la connexion marche alors on essaie de prendre le controle sinon on arrête le programme

    # Prendre le controle avec le mot de passe que l'on a défini
    await take_control("Kiks")
    await set_capture_parameters()
    capture = await create_new_capture()

    if capture is None:
        print("⚠️ Impossible de démarrer le streaming : connexion QTM absente.")
        return
    await start_streaming()

    try:
        while True:
            await asyncio.sleep(2)
    except KeyboardInterrupt:
        print("\n🛑 Interruption détectée. Déconnexion en cours...")
    finally:
        if qtm_connection:
            await qtm_connection.disconnect()
            print("✅ Déconnecté de QTM.")


if __name__ == "__main__":
    asyncio.run(main())  # Lancer la boucle principale
