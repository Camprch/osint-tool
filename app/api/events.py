# app/api/events.py
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlmodel import Session, select
from datetime import date, datetime
from typing import List, Optional, Dict, Tuple
from app.database import get_db
from app.models.message import Message
from .schemas import CountryEventsResponse, ZoneEvents, EventMessage
from .utils import normalize_country_names, COUNTRY_ALIASES, COUNTRY_COORDS

router = APIRouter()

@router.get(
    "/countries/{country}/all-events",
    response_model=CountryEventsResponse,
)
def get_country_all_events(
    country: str,
    session: Session = Depends(get_db),
):
    norm_country = country
    if not norm_country or norm_country not in COUNTRY_COORDS:
        raise HTTPException(status_code=404, detail="Pays non normalisé ou non géoréférencé")

    stmt = select(Message).where(
        Message.country.is_not(None),
    )
    msgs = session.exec(stmt).all()
    msgs = [m for m in msgs if norm_country in normalize_country_names(m.country, COUNTRY_ALIASES)]

    if not msgs:
        raise HTTPException(status_code=404, detail="Aucun événement pour ce pays")

    last_date = max(m.created_at for m in msgs).date()

    import unicodedata
    import re
    def norm(val):
        if val is None:
            return ""
        s = str(val).strip().lower()
        s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
        s = re.sub(r'\s+', ' ', s)
        return s

    def display_name(m):
        if m.region and m.region.strip():
            return m.region.strip()
        if m.location and m.location.strip():
            return m.location.strip()
        return "Zone inconnue"

    def norm_display_name(m):
        return norm(display_name(m))

    buckets: Dict[str, List[Message]] = {}
    for m in msgs:
        key = norm_display_name(m)
        buckets.setdefault(key, []).append(m)

    zones_payload: List[ZoneEvents] = []

    for key, items in buckets.items():
        name = display_name(items[0])
        event_messages: List[EventMessage] = []
        for m in items:
            url = None
            if m.channel and m.telegram_message_id:
                url = f"https://t.me/{m.channel}/{m.telegram_message_id}"

            full_text = (m.translated_text or m.raw_text or "").strip()
            preview = full_text[:277] + "..." if len(full_text) > 280 else full_text

            event_messages.append(
                EventMessage(
                    id=m.id,
                    telegram_message_id=m.telegram_message_id,
                    channel=m.channel,
                    title=m.title,
                    source=m.source,
                    orientation=m.orientation,
                    event_timestamp=m.event_timestamp,
                    created_at=m.created_at,
                    url=url,
                    translated_text=full_text,
                    preview=preview,
                )
            )

        zones_payload.append(
            ZoneEvents(
                region=name,
                location=None,
                messages_count=len(items),
                messages=event_messages,
            )
        )

    zones_payload.sort(key=lambda z: z.messages_count, reverse=True)

    return CountryEventsResponse(
        date=last_date,
        country=country,
        zones=zones_payload,
    )

@router.get(
    "/countries/{country}/latest-events",
    response_model=CountryEventsResponse,
)
def get_country_latest_events(
    country: str,
    session: Session = Depends(get_db),
):
    norm_country = country
    if not norm_country or norm_country not in COUNTRY_COORDS:
        raise HTTPException(status_code=404, detail="Pays non normalisé ou non géoréférencé")

    stmt_last = (
        select(Message.created_at, Message.country)
        .order_by(Message.created_at.desc())
    )
    rows = session.exec(stmt_last).all()
    last_date = None
    for created_at, raw_country in rows:
        norm_countries = normalize_country_names(raw_country, COUNTRY_ALIASES)
        if norm_country in norm_countries:
            last_date = created_at
            break
    if not last_date:
        raise HTTPException(status_code=404, detail="Aucun événement pour ce pays")

    target_date = last_date.date()

    start_dt = datetime.combine(target_date, datetime.min.time())
    end_dt = datetime.combine(target_date, datetime.max.time())

    stmt = select(Message).where(
        Message.created_at >= start_dt,
        Message.created_at <= end_dt,
    )
    msgs = session.exec(stmt).all()
    msgs = [m for m in msgs if norm_country in normalize_country_names(m.country, COUNTRY_ALIASES)]

    import unicodedata
    import re
    def norm(val):
        if val is None:
            return ""
        s = str(val).strip().lower()
        s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
        s = re.sub(r'\s+', ' ', s)
        return s

    buckets: Dict[Tuple[str, str], List[Message]] = {}
    for m in msgs:
        key = (norm(m.region), norm(m.location))
        buckets.setdefault(key, []).append(m)

    zones_payload: List[ZoneEvents] = []

    for (region_key, location_key), items in buckets.items():
        region = next((m.region for m in items if m.region), None)
        location = next((m.location for m in items if m.location), None)
        event_messages: List[EventMessage] = []
        for m in items:
            url = None
            if m.channel and m.telegram_message_id:
                url = f"https://t.me/{m.channel}/{m.telegram_message_id}"

            full_text = (m.translated_text or m.raw_text or "").strip()
            preview = full_text[:277] + "..." if len(full_text) > 280 else full_text

            event_messages.append(
                EventMessage(
                    id=m.id,
                    telegram_message_id=m.telegram_message_id,
                    channel=m.channel,
                    title=m.title,
                    source=m.source,
                    orientation=m.orientation,
                    event_timestamp=m.event_timestamp,
                    created_at=m.created_at,
                    url=url,
                    translated_text=full_text,
                    preview=preview,
                )
            )

        zones_payload.append(
            ZoneEvents(
                region=region,
                location=location,
                messages_count=len(items),
                messages=event_messages,
            )
        )

    zones_payload.sort(key=lambda z: z.messages_count, reverse=True)

    return CountryEventsResponse(
        date=target_date,
        country=country,
        zones=zones_payload,
    )

@router.get(
    "/countries/{country}/events",
    response_model=CountryEventsResponse,
)
def get_country_events(
    country: str,
    target_date: date = Query(..., alias="date"),
    session: Session = Depends(get_db),
):
    norm_country = country
    if not norm_country or norm_country not in COUNTRY_COORDS:
        raise HTTPException(status_code=404, detail="Pays non normalisé ou non géoréférencé")

    start_dt = datetime.combine(target_date, datetime.min.time())
    end_dt = datetime.combine(target_date, datetime.max.time())

    stmt = select(Message).where(
        Message.created_at >= start_dt,
        Message.created_at <= end_dt,
    )
    msgs = session.exec(stmt).all()
    msgs = [m for m in msgs if norm_country in normalize_country_names(m.country, COUNTRY_ALIASES)]

    import unicodedata
    import re
    def norm(val):
        if val is None:
            return ""
        s = str(val).strip().lower()
        s = ''.join(c for c in unicodedata.normalize('NFD', s) if unicodedata.category(c) != 'Mn')
        s = re.sub(r'\s+', ' ', s)
        return s

    buckets: Dict[Tuple[str, str], List[Message]] = {}
    for m in msgs:
        key = (norm(m.region), norm(m.location))
        buckets.setdefault(key, []).append(m)

    zones_payload: List[ZoneEvents] = []

    for (region_key, location_key), items in buckets.items():
        region = next((m.region for m in items if m.region), None)
        location = next((m.location for m in items if m.location), None)
        event_messages: List[EventMessage] = []
        for m in items:
            url = None
            if m.channel and m.telegram_message_id:
                url = f"https://t.me/{m.channel}/{m.telegram_message_id}"

            full_text = (m.translated_text or m.raw_text or "").strip()
            preview = full_text[:277] + "..." if len(full_text) > 280 else full_text

            event_messages.append(
                EventMessage(
                    id=m.id,
                    telegram_message_id=m.telegram_message_id,
                    channel=m.channel,
                    title=m.title,
                    source=m.source,
                    orientation=m.orientation,
                    event_timestamp=m.event_timestamp,
                    created_at=m.created_at,
                    url=url,
                    translated_text=full_text,
                    preview=preview,
                )
            )

        zones_payload.append(
            ZoneEvents(
                region=region,
                location=location,
                messages_count=len(items),
                messages=event_messages,
            )
        )

    zones_payload.sort(key=lambda z: z.messages_count, reverse=True)

    return CountryEventsResponse(
        date=target_date,
        country=country,
        zones=zones_payload,
    )
