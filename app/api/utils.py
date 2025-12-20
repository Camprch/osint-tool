# app/api/utils.py
import os
import json
from typing import Dict

# Fonction utilitaire pour charger les alias depuis countries.json et normaliser les noms de pays
def normalize_country_names(name: str, aliases: dict) -> list:
    if not name:
        return []
    names = [n.strip().lower() for n in name.split(',') if n.strip()]
    result = []
    for n in names:
        norm = aliases.get(n, None)
        if norm:
            result.append(norm)
    return result

COUNTRIES_JSON_PATH = os.path.join(os.path.dirname(__file__), '../../static/data/countries.json')
with open(COUNTRIES_JSON_PATH, encoding='utf-8') as f:
    _countries_data = json.load(f)
    COUNTRY_ALIASES = _countries_data.get('aliases', {})
    COUNTRY_COORDS = _countries_data.get('coordinates', {})
