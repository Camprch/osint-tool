# tools/init_telegram_string.py

from pathlib import Path
import sys
import asyncio

from telethon import TelegramClient
from telethon.sessions import StringSession

# Assure que le dossier racine est dans le path Python
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import get_settings

settings = get_settings()


async def main():
    print("\n[init_telegram_string] Initialisation de la session Telegram…")

    client = TelegramClient(
        StringSession(),                 # session en mémoire
        settings.telegram_api_id,
        settings.telegram_api_hash,
    )

    # Démarre la session → va te demander ton téléphone + code une seule fois
    await client.start()

    session_str = client.session.save()

    print("\n🎉 Ta TG_SESSION (à mettre dans GitHub Secrets) :\n")
    print(session_str)
    print("\n⚠️ NE LA PARTAGE JAMAIS PUBLIQUEMENT.\n")


if __name__ == "__main__":
    asyncio.run(main())
