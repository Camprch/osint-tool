# app/services/enrichment.py
from typing import List, Dict, Any, Optional
import json

from openai import OpenAI
from app.config import get_settings

settings = get_settings()
client = OpenAI(api_key=settings.openai_api_key)
MODEL_NAME = settings.openai_model
BATCH_SIZE = settings.batch_size

EXPECTED_FIELDS = ["country", "region", "location", "title", "source", "timestamp"]


def _empty_enrichment() -> Dict[str, Optional[str]]:
    return {
        "country": None,
        "region": None,
        "location": None,
        "title": None,
        "source": None,
        "timestamp": None,
    }


def _enrich_subbatch(items: List[Dict[str, Any]]) -> List[Dict[str, Optional[str]]]:
    """
    items: [{ "id": int, "text": str }]
    Retourne, dans le même ordre, une liste de dicts avec les champs EXPECTED_FIELDS.
    """
    if not items:
        return []

    header = (
        "Tu es un système d'extraction d'information OSINT.\n"
        "Pour chaque message ci-dessous, produis UNE LIGNE JSON (format JSONL) :\n"
        '{"id": <int>, "country": "...", "region": "...", "location": "...", '
        '"title": "...", "source": "...", "timestamp": "..."}\n\n'
        "Règles :\n"
        "- 'id' = identifiant fourni en entrée.\n"
        "- 'country' = pays principal impacté en français (\"Pays1\", \"Pays2\", ...), "
        "ou \"\" si incertain.\n"
        "- 'region' = zone large (province, région, etc.) ou \"\".\n"
        "- 'location' = ville / lieu précis ou \"\".\n"
        "- 'title' = phrase courte (8-18 mots) résumant l'événement.\n"
        "- 'source' = source explicite dans le texte, sinon \"\".\n"
        "- 'timestamp' = horodatage explicite en ISO 8601, sinon \"\".\n"
        "Pas de texte hors JSON, pas de commentaires.\n\n"
        "Messages :\n"
    )

    body = "\n".join(f"[{it['id']}] {it.get('text','')}" for it in items)
    prompt = header + body

    resp = client.responses.create(
        model=MODEL_NAME,
        input=prompt,
    )

    try:
        raw = resp.output_text
    except AttributeError:
        raw = str(resp)

    lines = [l.strip() for l in raw.splitlines() if l.strip()]

    id_to_index = {int(it["id"]): idx for idx, it in enumerate(items)}
    results: List[Dict[str, Optional[str]]] = [_empty_enrichment() for _ in items]
    seen_ids = set()

    for line in lines:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict) or "id" not in obj:
            continue
        try:
            obj_id = int(obj["id"])
        except Exception:
            continue
        if obj_id not in id_to_index or obj_id in seen_ids:
            continue

        filtered: Dict[str, Optional[str]] = {}
        for k in EXPECTED_FIELDS:
            v = obj.get(k, "")
            if v is None:
                v = ""
            elif not isinstance(v, str):
                v = str(v)
            filtered[k] = v

        results[id_to_index[obj_id]] = filtered
        seen_ids.add(obj_id)

    return results


def enrich_messages(messages: List[dict]) -> List[dict]:
    """
    Prend une liste de dicts avec 'translated_text' (ou 'text'),
    enrichit par batchs successifs.
    """
    if not messages:
        return messages

    total = len(messages)
    for start in range(0, total, BATCH_SIZE):
        end = min(start + BATCH_SIZE, total)
        sub = messages[start:end]

        items = [
            {"id": i, "text": (m.get("translated_text") or m.get("text") or "")}
            for i, m in enumerate(sub)
        ]

        enrichments = _enrich_subbatch(items)

        for msg, enr in zip(sub, enrichments):
            if enr:
                msg["country"] = enr.get("country") or None
                msg["region"] = enr.get("region") or None
                msg["location"] = enr.get("location") or None
                msg["title"] = enr.get("title") or None

    return messages
