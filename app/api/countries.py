# app/api/countries.py
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlmodel import Session, select
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Tuple
from app.database import get_db
from app.models.message import Message
from .schemas import CountryActivity, CountryStatus, ActiveCountriesResponse, CountryEventsResponse, ZoneEvents, EventMessage
from .utils import normalize_country_names, COUNTRY_ALIASES, COUNTRY_COORDS

router = APIRouter()

@router.get("/countries/active", response_model=ActiveCountriesResponse)
def get_active_countries(
    days: int = Query(30, ge=1),
    date_filter: Optional[date] = Query(None, alias="date"),
    session: Session = Depends(get_db),
):
    """
    Renvoie les pays qui ont des messages à une date précise (si 'date' fourni),
    sinon dans les X derniers jours, avec le nombre d'événements et la dernière date d'activité.
    Fournit aussi la liste des pays ignorés (non normalisés).
    """
    if date_filter:
        start_dt = datetime.combine(date_filter, datetime.min.time())
        end_dt = datetime.combine(date_filter, datetime.max.time())
        stmt = select(Message.country, Message.created_at).where(
            Message.created_at >= start_dt,
            Message.created_at <= end_dt,
            Message.country.is_not(None),
        )
    else:
        now = datetime.utcnow()
        start_dt = now - timedelta(days=days)
        stmt = select(Message.country, Message.created_at).where(
            Message.created_at >= start_dt,
            Message.country.is_not(None),
        )
    rows = session.exec(stmt).all()

    stats: Dict[str, Dict[str, object]] = {}
    ignored_countries = set()
    for country, created_at in rows:
        if not country:
            continue
        country = country.strip()
        if not country:
            continue
        norm_countries = normalize_country_names(country, COUNTRY_ALIASES)
        if not norm_countries:
            ignored_countries.add(country)
            continue
        d = created_at.date()
        for norm_country in norm_countries:
            if norm_country not in stats:
                stats[norm_country] = {"count": 0, "last_date": d}
            stats[norm_country]["count"] += 1
            if d > stats[norm_country]["last_date"]:
                stats[norm_country]["last_date"] = d

    result = [
        CountryStatus(
            country=c,
            events_count=v["count"],
            last_date=v["last_date"],
        )
        for c, v in stats.items() if c in COUNTRY_COORDS
    ]
    result.sort(key=lambda c: c.events_count, reverse=True)
    return ActiveCountriesResponse(countries=result, ignored_countries=sorted(ignored_countries))

@router.get("/countries", response_model=List[CountryActivity])
def get_countries_activity(
    target_date: date = Query(..., alias="date"),
    session: Session = Depends(get_db),
):
    """
    Compte les messages par pays pour une date donnée (sur created_at).
    """
    start_dt = datetime.combine(target_date, datetime.min.time())
    end_dt = datetime.combine(target_date, datetime.max.time())

    stmt = select(Message).where(
        Message.created_at >= start_dt,
        Message.created_at <= end_dt,
    )
    msgs = session.exec(stmt).all()

    counts: Dict[str, int] = {}
    for m in msgs:
        if not m.country:
            continue
        country = m.country.strip()
        if not country:
            continue
        counts[country] = counts.get(country, 0) + 1

    result = [
        CountryActivity(country=c, events_count=n)
        for c, n in sorted(counts.items(), key=lambda kv: kv[1], reverse=True)
    ]
    return result
