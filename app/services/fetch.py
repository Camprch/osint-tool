# app/services/fetch.py
from datetime import datetime, timedelta, timezone
from typing import List, Dict
import os  # 👈 ajouté

from telethon import TelegramClient
from telethon.errors import UsernameInvalidError, UsernameNotOccupiedError
from telethon.sessions import StringSession  # 👈 ajouté

from app.config import get_settings

settings = get_settings()


def _parse_sources_env() -> Dict[str, str | None]:
    """
    Lecture sécurisée de SOURCES_TELEGRAM depuis le .env.

    Format attendu :
        SOURCES_TELEGRAM="channel1:label1,channel2:label2,channel3"
    """
    raw = (settings.sources_telegram or "").strip()

    if not raw:
        return {}

    mapping: Dict[str, str | None] = {}

    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue

        # Retire @ pour éviter les fuites Telegram
        if part.startswith("@"):
            part = part[1:].strip()

        # Sépare canal / label
        if ":" in part:
            chan, label = part.split(":", 1)
        else:
            chan, label = part, None

        # Nettoyage du nom de canal
        import re
        chan = re.sub(r"[^A-Za-z0-9_]", "", chan)
        if not chan:
            continue

        mapping[chan] = (label.strip() if label else None)

    return mapping


async def fetch_raw_messages_24h() -> List[Dict]:
    """
    Récupère les messages des 24 dernières heures (max N par canal).
    """
    sources_map = _parse_sources_env()
    if not sources_map:
        print("[fetch] Aucun canal dans SOURCES_TELEGRAM.")
        return []

    max_per_channel = settings.max_messages_per_channel
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    # 🔑 Choix de la session :
    # - si TG_SESSION est présente (GitHub Actions) -> StringSession
    # - sinon, on utilise le fichier de session local (settings.telegram_session)
    session_str = os.environ.get("TG_SESSION")

    if session_str:
        # Mode CI / GitHub Actions
        client = TelegramClient(
            StringSession(session_str),
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )
    else:
        # Mode local (fichier .session classique)
        client = TelegramClient(
            settings.telegram_session,
            settings.telegram_api_id,
            settings.telegram_api_hash,
        )

    results: List[Dict] = []

    async with client:
        for chan, orient in sources_map.items():
            try:
                entity = await client.get_entity(chan)
            except (UsernameInvalidError, UsernameNotOccupiedError) as e:
                print(f"[fetch] Canal invalide ou introuvable : {chan} ({e})")
                continue
            except Exception as e:
                print(f"[fetch] Erreur get_entity({chan}) : {e}")
                continue

            try:
                msgs = await client.get_messages(entity, limit=max_per_channel)
            except Exception as e:
                print(f"[fetch] Erreur get_messages({chan}) : {e}")
                continue

            for m in msgs:
                dt = getattr(m, "date", None)
                if dt is None:
                    continue
                if dt < cutoff:
                    continue

                text = getattr(m, "message", "") or ""
                if not text.strip():
                    continue

                real_source = getattr(entity, "title", None) or getattr(entity, "username", chan)

                results.append(
                    {
                        "source": real_source,
                        "channel": chan,
                        "orientation": (orient or "inconnu").lower(),
                        "text": text,
                        "date": dt,
                        "telegram_message_id": m.id,
                    }
                )

    print(f"[fetch] Total messages 24h récupérés : {len(results)}")
    return results
