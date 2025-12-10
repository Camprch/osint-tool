# app/api/routes.py
from datetime import date, datetime, timedelta
from typing import List, Optional, Dict, Tuple

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlmodel import Session, select

from app.database import get_db
from app.models.message import Message

router = APIRouter()


class DatesResponse(BaseModel):
    dates: List[date]


class CountryActivity(BaseModel):
    country: str
    events_count: int


class CountryStatus(BaseModel):
    country: str
    events_count: int
    last_date: date


class EventMessage(BaseModel):
    id: int
    telegram_message_id: Optional[int]
    channel: Optional[str]
    title: Optional[str]
    source: Optional[str]
    orientation: Optional[str]
    event_timestamp: Optional[datetime]
    created_at: datetime
    url: Optional[str]
    translated_text: Optional[str] = None
    preview: str


class ZoneEvents(BaseModel):
    region: Optional[str]
    location: Optional[str]
    messages_count: int
    messages: List[EventMessage]


class CountryEventsResponse(BaseModel):
    date: date
    country: str
    zones: List[ZoneEvents]


@router.get("/dates", response_model=DatesResponse)
def get_available_dates(session: Session = Depends(get_db)):
    """
    Renvoie les 10 dernières dates (sur created_at) où il y a des messages.
    """
    stmt = select(Message.created_at).order_by(Message.created_at.desc())
    rows = session.exec(stmt).all()

    seen = set()
    dates_list: List[date] = []
    for dt in rows:
        d = dt.date()
        if d not in seen:
            seen.add(d)
            dates_list.append(d)
        if len(dates_list) >= 10:
            break

    return DatesResponse(dates=dates_list)

@router.get("/countries/active", response_model=List[CountryStatus])
def get_active_countries(
    days: int = Query(30, ge=1),
    session: Session = Depends(get_db),
):
    """
    Renvoie les pays qui ont des messages dans les X derniers jours,
    avec le nombre d'événements et la dernière date d'activité.
    """
    now = datetime.utcnow()
    start_dt = now - timedelta(days=days)

    stmt = select(Message.country, Message.created_at).where(
        Message.created_at >= start_dt,
        Message.country.is_not(None),
    )
    rows = session.exec(stmt).all()

    stats: Dict[str, Dict[str, object]] = {}
    for country, created_at in rows:
        if not country:
            continue
        country = country.strip()
        if not country:
            continue

        d = created_at.date()
        if country not in stats:
            stats[country] = {"count": 0, "last_date": d}
        stats[country]["count"] += 1
        if d > stats[country]["last_date"]:
            stats[country]["last_date"] = d

    result = [
        CountryStatus(
            country=c,
            events_count=v["count"],
            last_date=v["last_date"],
        )
        for c, v in stats.items()
    ]
    # tri optionnel : pays les plus actifs en premier
    result.sort(key=lambda c: c.events_count, reverse=True)
    return result

@router.get(
    "/countries/{country}/latest-events",
    response_model=CountryEventsResponse,
)
def get_country_latest_events(
    country: str,
    session: Session = Depends(get_db),
):
    """
    Liste les événements pour un pays à la date la plus récente (sur created_at).
    """
    # 1) On cherche la dernière date pour ce pays
    stmt_last = (
        select(Message.created_at)
        .where(Message.country == country)
        .order_by(Message.created_at.desc())
    )
    last_created_at = session.exec(stmt_last).first()
    if not last_created_at:
        raise HTTPException(status_code=404, detail="Aucun événement pour ce pays")

    target_date = last_created_at.date()

    # 2) On reprend la logique de get_country_events
    start_dt = datetime.combine(target_date, datetime.min.time())
    end_dt = datetime.combine(target_date, datetime.max.time())

    stmt = select(Message).where(
        Message.created_at >= start_dt,
        Message.created_at <= end_dt,
        Message.country == country,
    )
    msgs = session.exec(stmt).all()

    buckets: Dict[Tuple[Optional[str], Optional[str]], List[Message]] = {}
    for m in msgs:
        key = (m.region, m.location)
        buckets.setdefault(key, []).append(m)

    zones_payload: List[ZoneEvents] = []

    for (region, location), items in buckets.items():
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


@router.get(
    "/countries/{country}/events",
    response_model=CountryEventsResponse,
)
def get_country_events(
    country: str,
    target_date: date = Query(..., alias="date"),
    session: Session = Depends(get_db),
):
    """
    Liste des événements pour un pays + date (groupés par région / location).
    """
    start_dt = datetime.combine(target_date, datetime.min.time())
    end_dt = datetime.combine(target_date, datetime.max.time())

    stmt = select(Message).where(
        Message.created_at >= start_dt,
        Message.created_at <= end_dt,
        Message.country == country,
    )
    msgs = session.exec(stmt).all()

    buckets: Dict[Tuple[Optional[str], Optional[str]], List[Message]] = {}
    for m in msgs:
        key = (m.region, m.location)
        buckets.setdefault(key, []).append(m)

    zones_payload: List[ZoneEvents] = []

    for (region, location), items in buckets.items():
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
