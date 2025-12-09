# app/services/translation.py
from typing import List
from openai import OpenAI

from app.config import get_settings

settings = get_settings()
client = OpenAI(api_key=settings.openai_api_key)
MODEL_NAME = settings.openai_model
# Nombre de messages par appel OpenAI
BATCH_SIZE = settings.batch_size


def _translate_subbatch(texts: List[str]) -> List[str]:
    """
    Traduit un sous-batch de messages vers un français naturel.
    Texte => texte, même ordre.
    """
    if not texts:
        return []

    header = (
        "Tu es un traducteur professionnel.\n"
        "Je vais te donner une liste de messages numérotés.\n"
        "Pour chaque message, réponds STRICTEMENT en JSON Lines :\n"
        '{"index": <int>, "translation": "<texte traduit>"}\n'
        "Un seul objet JSON par ligne, même ordre que les index.\n"
        "Pas de texte hors JSON, pas de commentaire.\n"
        "IMPORTANT : Traduis chaque message en français naturel, même si le texte original est en anglais ou dans une autre langue.\n"
        "Si un message contient des noms propres, hashtags, expressions spécifiques ou éléments non traduisibles, conserve-les tels quels et mets-les entre guillemets dans la traduction française.\n"
        "Messages :\n"
    )

    body_lines = []
    for i, txt in enumerate(texts):
        body_lines.append(f"[{i}] {txt}")
    prompt = header + "\n".join(body_lines)

    resp = client.responses.create(
        model=MODEL_NAME,
        input=prompt,
    )

    try:
        raw = resp.output_text
    except AttributeError:
        raw = str(resp)

    import json
    lines = [l.strip() for l in raw.splitlines() if l.strip()]
    translations = [""] * len(texts)

    for line in lines:
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(obj, dict):
            continue
        if "index" not in obj or "translation" not in obj:
            continue
        idx = obj["index"]
        if not isinstance(idx, int):
            continue
        if 0 <= idx < len(texts):
            translations[idx] = str(obj["translation"])

    # fallback si certains indices sont vides => on remet le texte d’origine
    for i, t in enumerate(translations):
        if not t:
            translations[i] = texts[i]

    return translations


def translate_messages(messages: List[dict]) -> List[dict]:
    """
    Prend une liste de dicts avec au moins 'text',
    ajoute 'translated_text' en batchs successifs.
    Modifie la liste en place et la renvoie.
    """
    if not messages:
        return messages

    total = len(messages)
    for start in range(0, total, BATCH_SIZE):
        end = min(start + BATCH_SIZE, total)
        sub = messages[start:end]
        texts = [m.get("text", "") for m in sub]

        translations = _translate_subbatch(texts)

        for msg, trans in zip(sub, translations):
            msg["translated_text"] = trans

    return messages
