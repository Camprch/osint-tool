# tools/run_pipeline.py
import asyncio
from pathlib import Path
from datetime import datetime, timedelta

import sys

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.database import init_db, get_session
from app.models.message import Message
from sqlmodel import select

from app.services.fetch import fetch_raw_messages_24h
from app.services.translation import translate_messages
from app.services.enrichment import enrich_messages
from app.services.dedupe import dedupe_messages


def store_messages(messages: list[dict]) -> None:
    """
    Enregistre les messages dans SQLite.
    """
    from datetime import datetime, timezone
    with get_session() as session:
        for msg in messages:
            # Assure que event_timestamp est un datetime timezone-aware ou None
            event_timestamp = msg.get("date")
            if event_timestamp is not None:
                if isinstance(event_timestamp, str):
                    try:
                        # Essaye de parser l'ISO format
                        event_timestamp = datetime.fromisoformat(event_timestamp)
                    except Exception:
                        event_timestamp = None
                if isinstance(event_timestamp, datetime):
                    if event_timestamp.tzinfo is None:
                        # On force UTC si pas de tzinfo
                        event_timestamp = event_timestamp.replace(tzinfo=timezone.utc)
            m = Message(
                source=msg.get("source") or "unknown",
                channel=msg.get("channel"),
                raw_text=msg.get("text", ""),
                translated_text=msg.get("translated_text"),
                country=msg.get("country"),
                region=msg.get("region"),
                location=msg.get("location"),
                title=msg.get("title"),
                event_timestamp=event_timestamp,
                telegram_message_id=msg.get("telegram_message_id"),
                orientation=msg.get("orientation"),
            )
            session.add(m)
        session.commit()
    print(f"[pipeline] {len(messages)} messages stockés.")


def filter_existing_messages(messages: list[dict]) -> list[dict]:
    """
    Filtre les messages déjà présents en base (par channel + telegram_message_id).
    """
    if not messages:
        return []
    keys = [(m.get("channel"), m.get("telegram_message_id")) for m in messages]
    channels = set(k[0] for k in keys if k[0] is not None)
    ids = set(k[1] for k in keys if k[1] is not None)
    if not channels or not ids:
        return messages
    with get_session() as session:
        stmt = select(Message.channel, Message.telegram_message_id).where(
            Message.channel.in_(channels),
            Message.telegram_message_id.in_(ids)
        )
        existing = set((row[0], row[1]) for row in session.exec(stmt).all())
    filtered = [m for m in messages if (m.get("channel"), m.get("telegram_message_id")) not in existing]
    print(f"[pipeline] {len(messages)-len(filtered)} messages déjà en base ignorés.")
    return filtered


def delete_old_messages(days: int = 10) -> None:
    """
    Supprime les messages dont l'event_timestamp est plus vieux que X jours.
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    with get_session() as session:
        from sqlmodel import delete

        # On supprime directement en SQL, pas besoin de charger les objets en mémoire
        stmt = delete(Message).where(Message.event_timestamp < cutoff)
        result = session.exec(stmt)
        session.commit()

    deleted = getattr(result, "rowcount", None)
    print(f"[pipeline] Messages plus vieux que {days} jours supprimés ({deleted}).")


async def run_pipeline_once():
    print("[pipeline] init_db()")
    init_db()

    print("[pipeline] fetch_raw_messages_24h()")

    raw_messages = await fetch_raw_messages_24h()
    if not raw_messages:
        print("[pipeline] Aucun message à traiter.")
        return

    # Filtrage des messages déjà présents en base
    raw_messages = filter_existing_messages(raw_messages)
    if not raw_messages:
        print("[pipeline] Tous les messages sont déjà en base. Rien à faire.")
        return

    print("[pipeline] translate_messages()")
    translate_messages(raw_messages)
    # Log des traductions pour diagnostic
    for i, msg in enumerate(raw_messages[:10]):
        print(f"[trad] {i}: EN: {msg.get('text', '')[:60]} | FR: {msg.get('translated_text', '')[:60]}")

    print("[pipeline] enrich_messages()")
    enrich_messages(raw_messages)

    print("[pipeline] dedupe_messages()")
    deduped = dedupe_messages(raw_messages)
    print(f"[pipeline] Après déduplication : {len(deduped)} messages")

    print("[pipeline] store_messages()")
    store_messages(deduped)

    print("[pipeline] delete_old_messages()")
    delete_old_messages(days=10)

    print("[pipeline] Pipeline terminé.")


if __name__ == "__main__":
    asyncio.run(run_pipeline_once())
