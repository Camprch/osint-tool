# app/api/schemas.py
from datetime import date, datetime
from typing import List, Optional
from pydantic import BaseModel

class DatesResponse(BaseModel):
    dates: List[date]

class CountryActivity(BaseModel):
    country: str
    events_count: int

class CountryStatus(BaseModel):
    country: str
    events_count: int
    last_date: date

class ActiveCountriesResponse(BaseModel):
    countries: List[CountryStatus]
    ignored_countries: List[str]

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
