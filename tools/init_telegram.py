# tools/init_telegram.py
from pathlib import Path
import sys

from telethon import TelegramClient

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.config import get_settings

settings = get_settings()


async def main():
    client = TelegramClient(
        settings.telegram_session,
        settings.telegram_api_id,
        settings.telegram_api_hash,
    )
    await client.start()
    print("[init_telegram] Session initialisée. Fichier :", settings.telegram_session)


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
