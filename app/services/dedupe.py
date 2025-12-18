# app/services/dedupe.py
from typing import List, Dict


def dedupe_messages(messages: List[Dict]) -> List[Dict]:
    """
    Déduplication très simple :
    - si on a un title : clé = (source, channel, country, title)
    - sinon : clé = (source, channel, translated_text / raw_text)
    On garde le premier, on jette les suivants.
    """
    seen = set()
    result: List[Dict] = []

    for msg in messages:
        source = msg.get("source")
        channel = msg.get("channel")
        country = msg.get("country") or ""

        title = (msg.get("title") or "").strip()
        text = (msg.get("translated_text") or msg.get("raw_text") or msg.get("text") or "").strip()

        if title:
            key = ("title", source, channel, country, title)
        else:
            key = ("text", source, channel, country, text)

        if key in seen:
            continue
        seen.add(key)
        result.append(msg)

    return result
