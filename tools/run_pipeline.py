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

from app.services.fetch import fetch_raw_messages_24h
from app.services.translation import translate_messages
from app.services.enrichment import enrich_messages
from app.services.dedupe import dedupe_messages


def store_messages(messages: list[dict]) -> None:
    """
    Enregistre les messages dans SQLite.
    """
    with get_session() as session:
        for msg in messages:
            m = Message(
                source=msg.get("source") or "unknown",
                channel=msg.get("channel"),
                raw_text=msg.get("text", ""),
                translated_text=msg.get("translated_text"),
                country=msg.get("country"),
                region=msg.get("region"),
                location=msg.get("location"),
                title=msg.get("title"),
                event_timestamp=msg.get("date"),
                telegram_message_id=msg.get("telegram_message_id"),
                orientation=msg.get("orientation"),
            )
            session.add(m)
        session.commit()
    print(f"[pipeline] {len(messages)} messages stockés.")


def delete_old_messages(days: int = 10) -> None:
    """
    Supprime les messages plus vieux que X jours (sur created_at).
    """
    cutoff = datetime.utcnow() - timedelta(days=days)
    with get_session() as session:
        from sqlmodel import select, delete

        stmt = select(Message).where(Message.created_at < cutoff)
        old_msgs = session.exec(stmt).all()
        if not old_msgs:
            return
        ids = [m.id for m in old_msgs if m.id is not None]
        if not ids:
            return
        session.exec(delete(Message).where(Message.id.in_(ids)))
        session.commit()
    print(f"[pipeline] Messages plus vieux que {days} jours supprimés ({len(ids)}).")


async def run_pipeline_once():
    print("[pipeline] init_db()")
    init_db()

    print("[pipeline] fetch_raw_messages_24h()")
    raw_messages = await fetch_raw_messages_24h()
    if not raw_messages:
        print("[pipeline] Aucun message à traiter.")
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
